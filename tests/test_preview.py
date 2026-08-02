"""预览窗格：异步解码、信息行、容错、让路。"""

from __future__ import annotations

import pytest

from acdseen.preview import PreviewPane
from conftest import pump


@pytest.fixture
def pane(qapp):
    p = PreviewPane()
    p.resize(300, 240)
    p.show()
    yield p
    p.close()


def test_显示选中图片(qapp, pics, pane):
    pane.show_path(pics / "IMG_000.jpg")
    assert pump(qapp, 6000, lambda: pane._img is not None)
    assert not pane._error


def test_信息行报原图尺寸而非预览尺寸(qapp, pics, pane):
    """回归：预览图是按窗格大小缩过的，拿它的尺寸会报出错的数字。

    4000×3000 的图在 300px 窗格里曾显示成 300×225，和状态栏对不上。
    """
    big = pics / "IMG_002.bmp"          # 2400x1800
    pane.show_path(big)
    assert pump(qapp, 8000, lambda: pane._img is not None)

    assert max(pane._img.width(), pane._img.height()) < 2400, "预览图应当是缩小的"
    line = pane._info_line()
    assert "2400×1800" in line, f"信息行报了预览图的尺寸：{line}"


def test_信息行在解码完成前就有尺寸(qapp, pics, pane):
    """尺寸只读文件头，不必等像素解完。"""
    pane.show_path(pics / "IMG_000.jpg")
    assert "1920×1080" in pane._info_line()


def test_切换图片更新信息行(qapp, pics, pane):
    pane.show_path(pics / "IMG_000.jpg")
    assert "IMG_000.jpg" in pane._info_line()
    pane.show_path(pics / "IMG_001.png")
    assert "IMG_001.png" in pane._info_line()
    assert "800×600" in pane._info_line()


def test_损坏文件标记错误不崩溃(qapp, pics, pane):
    pane.show_path(pics / "broken.jpg")
    assert pump(qapp, 6000, lambda: pane._error)
    assert pane._img is None
    pane.repaint()      # 错误态也得能画


def test_clear清空(qapp, pics, pane):
    pane.show_path(pics / "IMG_000.jpg")
    pump(qapp, 4000, lambda: pane._img is not None)
    pane.clear()
    assert pane._path is None
    assert pane._info_line() == ""
    pane.repaint()


def test_重复设同一路径不重新解码(qapp, pics, pane):
    p = pics / "IMG_000.jpg"
    pane.show_path(p)
    assert pump(qapp, 6000, lambda: pane._img is not None)
    gen = pane._generation
    pane.show_path(p)
    assert pane._generation == gen, "同一张图不该重新排解码任务"


def test_暂停后恢复会重新加载(qapp, pics, pane):
    pane.show_path(pics / "IMG_000.jpg")
    assert pump(qapp, 6000, lambda: pane._img is not None)

    pane.set_paused(True)
    assert pane._img is None, "暂停应作废在飞任务并清掉当前图"

    pane.set_paused(False)
    assert pump(qapp, 6000, lambda: pane._img is not None), "恢复后没重新加载"


def test_空路径显示提示不崩溃(qapp, pane):
    pane.show_path(None)
    assert pane._info_line() == ""
    pane.repaint()
