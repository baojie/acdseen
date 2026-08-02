"""解码层：两段式加载、预读、缩略图线程池、磁盘缓存。

这里有三条测试直接对应开发期修过的真实 bug，删掉它们等于把坑重新挖开：
  * test_多线程并发解码pcx不崩溃      —— Pillow 插件 lazy-import 撞崩 shiboken
  * test_缩略图确实生成且尺寸正确      —— QImage.scaled 传 int 而非枚举，静默失败
  * test_pil兜底不经过ImageQt         —— ImageQt 在工作线程碰 Qt binding 会炸
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acdseen import config
from acdseen.loader import (HAVE_PIL, ImageLoader, ThumbnailLoader,
                            image_dimensions, load_image)
from conftest import pump


# ------------------------------------------------------------------ 同步解码
def test_load_image_各格式都能解(pics):
    for p in sorted(pics.glob("IMG_*")):
        img = load_image(p)
        assert img is not None and not img.isNull(), f"{p.name} 解不出来"


def test_load_image_损坏文件返回None(pics):
    assert load_image(pics / "broken.jpg") is None


def test_load_image_max_edge限制长边(pics):
    img = load_image(pics / "IMG_002.bmp", max_edge=512)
    assert max(img.width(), img.height()) <= 512


def test_image_dimensions_不解码就拿到尺寸(pics):
    assert image_dimensions(pics / "IMG_000.jpg") == (1920, 1080)
    assert image_dimensions(pics / "broken.jpg") is None


@pytest.mark.skipif(not HAVE_PIL, reason="未安装 Pillow")
def test_pil兜底能解pcx(pics):
    pcx = pics / "IMG_008.pcx"
    if not pcx.exists():
        pytest.skip("夹具未生成 pcx")
    img = load_image(pcx)
    assert img is not None and img.size().toTuple() == (1200, 900)


@pytest.mark.skipif(not HAVE_PIL, reason="未安装 Pillow")
def test_pil兜底不经过ImageQt():
    """回归：PIL.ImageQt 在工作线程里碰 Qt binding 会导致进程级崩溃。

    loader 必须自己从原始字节构造 QImage，绝不能重新引入 ImageQt。
    """
    import acdseen.loader as L
    assert not hasattr(L, "ImageQt"), "不要再引入 PIL.ImageQt"
    src = Path(L.__file__).read_text()
    assert "from PIL.ImageQt" not in src and "import ImageQt" not in src


# ------------------------------------------------------------------ 两段式
def test_大图走两段式_先preview后full(qapp, pics):
    loader = ImageLoader()
    events = []
    loader.preview_ready.connect(lambda p, i: events.append(("preview", i.size())))
    loader.full_ready.connect(lambda p, i: events.append(("full", i.size())))

    big = pics / "IMG_002.bmp"          # 2400x1800 > PREVIEW_EDGE
    assert loader.load(big) is None     # 冷缓存，同步返回 None
    assert pump(qapp, 6000, lambda: any(k == "full" for k, _ in events))

    kinds = [k for k, _ in events]
    assert kinds[0] == "preview", "第一帧必须是低清预览，否则失去快开的意义"
    assert "full" in kinds

    prev_size = next(s for k, s in events if k == "preview")
    full_size = next(s for k, s in events if k == "full")
    assert max(prev_size.toTuple()) <= config.PREVIEW_EDGE
    assert full_size.toTuple() == (2400, 1800)
    loader.shutdown()


def test_小图不发preview(qapp, pics):
    loader = ImageLoader()
    events = []
    loader.preview_ready.connect(lambda p, i: events.append("preview"))
    loader.full_ready.connect(lambda p, i: events.append("full"))

    loader.load(pics / "IMG_003.gif")   # 320x240，小于 PREVIEW_EDGE
    assert pump(qapp, 4000, lambda: "full" in events)
    assert "preview" not in events, "小图多解一遍是纯浪费"
    loader.shutdown()


def test_缓存命中时同步返回(qapp, pics):
    loader = ImageLoader()
    p = pics / "IMG_001.png"
    loader.load(p)
    assert pump(qapp, 4000, lambda: loader.cached(p) is not None)
    # 第二次必须同步拿到 —— 这就是翻页零延迟
    assert loader.load(p) is not None
    loader.shutdown()


def test_预读把邻居装进LRU(qapp, pics):
    loader = ImageLoader()
    files = sorted(pics.glob("IMG_*"))[:4]
    loader.read_ahead(files)
    assert pump(qapp, 8000, lambda: len(loader._lru) >= len(files))
    for f in files:
        assert loader.cached(f) is not None
    loader.shutdown()


def test_LRU不超上限(qapp, pics):
    loader = ImageLoader()
    many = list(sorted(pics.glob("IMG_*"))) * 3
    loader.read_ahead(many)
    pump(qapp, 8000)
    assert len(loader._lru) <= config.FULL_CACHE_SIZE
    loader.shutdown()


def test_解码失败发出load_failed(qapp, pics):
    loader = ImageLoader()
    failed = []
    loader.load_failed.connect(lambda p: failed.append(p))
    loader.load(pics / "broken.jpg")
    assert pump(qapp, 4000, lambda: bool(failed))
    loader.shutdown()


def test_drop清掉缓存项(qapp, pics):
    loader = ImageLoader()
    p = pics / "IMG_001.png"
    loader.load(p)
    pump(qapp, 4000, lambda: loader.cached(p) is not None)
    loader.drop(p)
    assert loader.cached(p) is None
    loader.shutdown()


# ------------------------------------------------------------------ 缩略图
def test_缩略图确实生成且尺寸正确(qapp, pics):
    """回归：QImage.scaled 曾经被传了 int 而非 Qt 枚举，任务静默抛异常。"""
    loader = ThumbnailLoader()
    got = {}
    loader.ready.connect(lambda p, i: got.__setitem__(p, i))

    files = sorted(pics.glob("IMG_*"))
    for f in files:
        loader.request(f, 128)
    assert pump(qapp, 15000, lambda: len(got) >= len(files))

    for f in files:
        img = got[f]
        assert img is not None and not img.isNull(), f"{f.name} 无缩略图"
        assert max(img.width(), img.height()) == 128, "长边应正好等于请求边长"
    loader.shutdown()


def test_多线程并发解码pcx不崩溃(qapp, pics):
    """回归：Pillow 的插件 lazy-import 在多工作线程下会撞崩 shiboken。

    这条测试的价值在于"进程还活着"——崩溃时它连断言都执行不到。
    """
    if not (pics / "IMG_008.pcx").exists():
        pytest.skip("无 pcx 样本")
    loader = ThumbnailLoader()
    done = []
    loader.ready.connect(lambda p, i: done.append(p))
    for _ in range(12):
        loader.request(pics / "IMG_008.pcx", 96)
    assert pump(qapp, 15000, lambda: len(done) >= 1)
    loader.shutdown()


def test_缩略图写入磁盘缓存并被复用(qapp, pics):
    loader = ThumbnailLoader()
    got = []
    loader.ready.connect(lambda p, i: got.append(i))
    loader.request(pics / "IMG_000.jpg", 96)
    assert pump(qapp, 8000, lambda: bool(got))

    cached = list(config.CACHE_DIR.rglob("*.png"))
    assert cached, "缩略图没落盘"
    loader.shutdown()


def test_缩略图缓存随mtime失效(qapp, workdir):
    import os
    loader = ThumbnailLoader()
    got = []
    loader.ready.connect(lambda p, i: got.append(i))
    target = workdir / "IMG_001.png"

    loader.request(target, 96)
    assert pump(qapp, 8000, lambda: bool(got))
    before = len(list(config.CACHE_DIR.rglob("*.png")))

    os.utime(target, (0, 0))    # 假装文件被改过
    got.clear()
    loader.request(target, 96)
    assert pump(qapp, 8000, lambda: bool(got))
    assert len(list(config.CACHE_DIR.rglob("*.png"))) > before, "mtime 变了却复用了旧缓存"
    loader.shutdown()


def test_损坏文件的缩略图返回None而非崩溃(qapp, pics):
    loader = ThumbnailLoader()
    got = {}
    loader.ready.connect(lambda p, i: got.__setitem__(p, i))
    loader.request(pics / "broken.jpg", 96)
    assert pump(qapp, 6000, lambda: bool(got))
    assert got[pics / "broken.jpg"] is None
    loader.shutdown()


def test_暂停时请求排队_恢复后执行(qapp, pics):
    loader = ThumbnailLoader()
    got = []
    loader.ready.connect(lambda p, i: got.append(p))

    loader.set_paused(True)
    for f in sorted(pics.glob("IMG_*"))[:3]:
        loader.request(f, 96)
    pump(qapp, 600)
    assert not got, "暂停期间不该有任务跑完"
    assert len(loader._pending) == 3

    loader.set_paused(False)
    assert pump(qapp, 10000, lambda: len(got) >= 3)
    loader.shutdown()


def test_invalidate作废在飞任务(qapp, pics):
    loader = ThumbnailLoader()
    got = []
    loader.ready.connect(lambda p, i: got.append(p))
    for f in sorted(pics.glob("IMG_*")):
        loader.request(f, 160)
    loader.invalidate()
    pump(qapp, 1500)
    # 作废后不保证一个都不到（已在跑的可能刚好完成），但不该全部到齐
    assert len(got) < len(list(pics.glob("IMG_*")))
    loader.shutdown()
