"""Pure functions: formatting, sorting, format detection. No GUI needed."""

from __future__ import annotations

from pathlib import Path

import pytest

from acdseen import config
from acdseen.util import (format_size, human_dims, is_image, list_images,
                          natural_key)


@pytest.mark.parametrize("n,expected", [
    (0, "0 B"), (512, "512 B"), (1024, "1.0 KB"),
    (1536, "1.5 KB"), (1024 * 1024, "1.0 MB"),
])
def test_format_size(n, expected):
    assert format_size(n) == expected


def test_format_size_大数值不带小数():
    # Decimal places above three digits would be too noisy
    assert format_size(500 * 1024) == "500 KB"


def test_human_dims():
    assert human_dims(800, 600) == "800×600"          # not shown below 1MP
    assert human_dims(4000, 3000) == "4000×3000 (12.0MP)"


def test_is_image():
    assert is_image(Path("a.JPG"))       # case-insensitive
    assert is_image(Path("a.pcx"))
    assert not is_image(Path("a.txt"))
    assert not is_image(Path("a"))


def test_natural_key_数字按数值排序():
    names = ["IMG_10.jpg", "IMG_2.jpg", "IMG_1.jpg"]
    assert sorted(names, key=natural_key) == ["IMG_1.jpg", "IMG_2.jpg", "IMG_10.jpg"]


def test_list_images_默认自然排序(pics):
    names = [p.name for p in list_images(pics)]
    assert names == sorted(names, key=natural_key)
    # IMG_010 must sort after IMG_007 -- lexicographic order would put it before IMG_002
    assert names.index("IMG_010.jpg") > names.index("IMG_007.bmp")


def test_list_images_只收图片(pics, tmp_path):
    d = tmp_path / "mixed"
    d.mkdir()
    (d / "a.png").write_bytes((pics / "IMG_001.png").read_bytes())
    (d / "notes.txt").write_text("hi")
    (d / "sub").mkdir()
    assert [p.name for p in list_images(d)] == ["a.png"]


def test_list_images_按大小和时间排序(pics):
    by_size = list_images(pics, config.SORT_SIZE)
    sizes = [p.stat().st_size for p in by_size]
    assert sizes == sorted(sizes)

    reverse = list_images(pics, config.SORT_SIZE, reverse=True)
    assert [p.name for p in reverse] == [p.name for p in by_size][::-1]


def test_list_images_目录不存在不抛异常(tmp_path):
    assert list_images(tmp_path / "nope") == []


# ------------------------------------------------------------------ sorting
def test_按宽高与像素总数排序(pics):
    from acdseen.util import image_size
    for key, metric in ((config.SORT_WIDTH, lambda p: image_size(p)[0]),
                        (config.SORT_HEIGHT, lambda p: image_size(p)[1]),
                        (config.SORT_PIXELS, lambda p: image_size(p)[0] * image_size(p)[1])):
        got = [metric(p) for p in list_images(pics, key) if metric(p)]
        assert got == sorted(got), f"排序键 {key} 没排好：{got}"


def test_尺寸排序倒序(pics):
    from acdseen.util import image_size
    asc = [p for p in list_images(pics, config.SORT_WIDTH) if image_size(p)[0]]
    desc = [p for p in list_images(pics, config.SORT_WIDTH, reverse=True) if image_size(p)[0]]
    assert desc == list(reversed(asc))


def test_读不出尺寸的文件不炸(pics):
    """broken.jpg can't have its size read; it should be treated as 0x0 and sorted first, not raise."""
    order = list_images(pics, config.SORT_PIXELS)
    assert order[0].name == "broken.jpg"


def test_随机排序同seed稳定(pics):
    a = list_images(pics, config.SORT_RANDOM, seed=7)
    b = list_images(pics, config.SORT_RANDOM, seed=7)
    assert a == b, "同一个 seed 必须排出同一个顺序，否则删张图就把网格重洗了"
    assert sorted(a) == sorted(list_images(pics, config.SORT_NAME)), "一张都不能丢"


def test_随机排序换seed会变(pics):
    assert len(list_images(pics, config.SORT_NAME)) >= 5, "样本太少，这条测试没意义"
    base = list_images(pics, config.SORT_RANDOM, seed=0)
    assert any(list_images(pics, config.SORT_RANDOM, seed=s) != base for s in range(1, 20)), \
        "换了 20 个 seed 顺序一次都没变"


def test_尺寸缓存按mtime失效(tmp_path, pics):
    import shutil
    from acdseen.util import image_size
    p = tmp_path / "x.png"
    shutil.copy(pics / "IMG_001.png", p)          # 800x600
    assert image_size(p) == (800, 600)
    shutil.copy(pics / "IMG_000.jpg", p.with_suffix(".jpg"))
    shutil.copy(pics / "IMG_006.jpg", p)          # swapped to 2560x1440, mtime changed too
    assert image_size(p) == (2560, 1440), "文件换了尺寸没跟着变，缓存 key 没带 mtime"
