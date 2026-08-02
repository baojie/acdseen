"""纯函数：格式化、排序、格式判定。不需要 GUI。"""

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
    # 三位数以上再带小数位就太吵了
    assert format_size(500 * 1024) == "500 KB"


def test_human_dims():
    assert human_dims(800, 600) == "800×600"          # 不足 1MP 不显示
    assert human_dims(4000, 3000) == "4000×3000 (12.0MP)"


def test_is_image():
    assert is_image(Path("a.JPG"))       # 大小写不敏感
    assert is_image(Path("a.pcx"))
    assert not is_image(Path("a.txt"))
    assert not is_image(Path("a"))


def test_natural_key_数字按数值排序():
    names = ["IMG_10.jpg", "IMG_2.jpg", "IMG_1.jpg"]
    assert sorted(names, key=natural_key) == ["IMG_1.jpg", "IMG_2.jpg", "IMG_10.jpg"]


def test_list_images_默认自然排序(pics):
    names = [p.name for p in list_images(pics)]
    assert names == sorted(names, key=natural_key)
    # IMG_010 必须排在 IMG_007 之后 —— 字典序会把它排到 IMG_002 前面
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
