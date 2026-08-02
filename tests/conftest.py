"""测试夹具。

两件必须隔离的事：
  * 缩略图磁盘缓存 —— 否则测试会写进用户的 ~/.cache
  * QSettings   —— 否则测试会改掉用户真实的窗口几何/上次目录
两者都在 session 级重定向到临时目录。
"""

from __future__ import annotations

import os
import time

# 必须在导入任何 Qt 模块之前设置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from acdseen import config
from acdseen.loader import warmup

# 覆盖测试用的图片矩阵：格式 × 尺寸，尺寸要跨过 PREVIEW_EDGE 两侧
_SPECS = [
    ("IMG_000.jpg", 1920, 1080),
    ("IMG_001.png", 800, 600),
    ("IMG_002.bmp", 2400, 1800),   # > PREVIEW_EDGE，走两段式
    ("IMG_003.gif", 320, 240),     # < PREVIEW_EDGE，单段
    ("IMG_004.tiff", 1600, 900),
    ("IMG_005.png", 640, 480),
    ("IMG_006.jpg", 2560, 1440),
    ("IMG_007.bmp", 500, 500),
    ("IMG_010.jpg", 800, 600),     # 用于验证自然排序：10 应排在 7 之后
]


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    warmup()
    yield app


@pytest.fixture(scope="session", autouse=True)
def _isolate(tmp_path_factory, qapp):
    """把缓存和设置引到临时目录，别碰用户的真实环境。"""
    cache = tmp_path_factory.mktemp("cache")
    config.CACHE_DIR = cache / "thumbs"

    settings_dir = tmp_path_factory.mktemp("settings")
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(settings_dir))
    yield


@pytest.fixture(autouse=True)
def _clean_settings(_isolate):
    """每个测试前清空 QSettings。

    Browser.closeEvent 会把排序方式、缩略图尺寸、上次目录写回去，
    不清的话前一个测试的状态会被下一个 Browser 的 _restore_state() 读进来，
    表现为莫名其妙的顺序错乱。
    """
    QSettings(config.ORG_NAME, config.APP_NAME).clear()
    yield
    QSettings(config.ORG_NAME, config.APP_NAME).clear()


def _qt_can_write(suffix: str) -> bool:
    from PySide6.QtGui import QImageWriter
    fmt = suffix.lstrip(".").lower().encode()
    return fmt in QImageWriter.supportedImageFormats()


def _draw_qt(path, w, h) -> None:
    img = QImage(w, h, QImage.Format_RGB888)
    img.fill(QColor((w * 7) % 256, (h * 11) % 256, 128))
    p = QPainter(img)
    p.setPen(Qt.white)
    # 画点内容，避免纯色图被编码器压成病态小文件
    for i in range(0, w, max(1, w // 20)):
        p.drawLine(i, 0, w - i, h)
    p.end()
    assert img.save(str(path)), f"无法写出 {path}"


def _draw_pil(path, w, h) -> bool:
    """Qt 写不了的格式（GIF 一律不能写，TIFF 取决于有没有 qtimageformats）
    退回 Pillow 生成。没装 Pillow 就返回 False，调用方跳过这一张。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False
    im = Image.new("RGB", (w, h), ((w * 7) % 256, (h * 11) % 256, 128))
    dr = ImageDraw.Draw(im)
    for i in range(0, w, max(1, w // 20)):
        dr.line([(i, 0), (w - i, h)], fill=(255, 255, 255))
    im.save(path)
    return True


@pytest.fixture(scope="session")
def pics(tmp_path_factory, qapp):
    """一个包含多种格式、多种尺寸，外加一个损坏文件的目录。

    格式覆盖到哪一步取决于环境：GIF 无论如何 Qt 都写不出，TIFF 要看
    有没有 qtimageformats 插件，PCX 只有 Pillow 认。写不出的就不生成，
    对应测试自然跳过 —— 总比夹具自己炸掉强。
    """
    d = tmp_path_factory.mktemp("pics")
    for name, w, h in _SPECS:
        target = d / name
        if _qt_can_write(target.suffix):
            _draw_qt(target, w, h)
        else:
            _draw_pil(target, w, h)

    # PCX：Qt 从不支持，纯粹用来验证 Pillow 兜底路径
    _draw_pil(d / "IMG_008.pcx", 1200, 900)

    # 故意损坏的文件：必须不崩溃，且被标记为解码失败
    (d / "broken.jpg").write_bytes(b"this is definitely not a jpeg")
    return d


@pytest.fixture
def workdir(pics, tmp_path):
    """pics 的可写副本 —— 会改文件的测试用这个，别污染 session 级夹具。"""
    import shutil
    d = tmp_path / "work"
    shutil.copytree(pics, d)
    return d


def pump(app, ms: int = 500, until=None) -> bool:
    """转事件循环最多 ms 毫秒；until 返回真就提前结束。

    返回是否满足了 until（没给 until 时恒为 True）。
    """
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        if until is not None and until():
            return True
        time.sleep(0.005)
    app.processEvents()
    return until is None or bool(until())
