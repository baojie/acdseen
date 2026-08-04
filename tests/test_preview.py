"""Preview pane: asynchronous decoding, info line, fault tolerance, yielding."""

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


def test_shows_the_selected_image(qapp, pics, pane):
    pane.show_path(pics / "IMG_000.jpg")
    assert pump(qapp, 6000, lambda: pane._img is not None)
    assert not pane._error


def test_info_line_reports_source_not_preview_dimensions(qapp, pics, pane):
    """Regression: the preview image is scaled to the pane, so its size would report a wrong number.

    A 4000x3000 image in a 300px pane used to show as 300x225, mismatching the status bar.
    """
    big = pics / "IMG_002.bmp"          # 2400x1800
    pane.show_path(big)
    assert pump(qapp, 8000, lambda: pane._img is not None)

    assert max(pane._img.width(), pane._img.height()) < 2400, "the preview should be a scaled-down image"
    line = pane._info_line()
    assert "2400×1800" in line, f"info line reported the preview size: {line}"


def test_info_line_has_dimensions_before_decode_finishes(qapp, pics, pane):
    """The size only reads the file header; no need to wait for pixels to decode."""
    pane.show_path(pics / "IMG_000.jpg")
    assert "1920×1080" in pane._info_line()


def test_changing_image_updates_the_info_line(qapp, pics, pane):
    pane.show_path(pics / "IMG_000.jpg")
    assert "IMG_000.jpg" in pane._info_line()
    pane.show_path(pics / "IMG_001.png")
    assert "IMG_001.png" in pane._info_line()
    assert "800×600" in pane._info_line()


def test_broken_file_marks_error_not_crash(qapp, pics, pane):
    pane.show_path(pics / "broken.jpg")
    assert pump(qapp, 6000, lambda: pane._error)
    assert pane._img is None
    pane.repaint()      # error state must be drawable too


def test_clear_empties_the_pane(qapp, pics, pane):
    pane.show_path(pics / "IMG_000.jpg")
    pump(qapp, 4000, lambda: pane._img is not None)
    pane.clear()
    assert pane._path is None
    assert pane._info_line() == ""
    pane.repaint()


def test_setting_the_same_path_twice_does_not_redecode(qapp, pics, pane):
    p = pics / "IMG_000.jpg"
    pane.show_path(p)
    assert pump(qapp, 6000, lambda: pane._img is not None)
    gen = pane._generation
    pane.show_path(p)
    assert pane._generation == gen, "the same image must not be queued for decoding again"


def test_resuming_after_a_pause_reloads(qapp, pics, pane):
    pane.show_path(pics / "IMG_000.jpg")
    assert pump(qapp, 6000, lambda: pane._img is not None)

    pane.set_paused(True)
    assert pane._img is None, "pausing must void in-flight tasks and clear the current image"

    pane.set_paused(False)
    assert pump(qapp, 6000, lambda: pane._img is not None), "nothing was reloaded after resuming"


def test_empty_path_shows_a_hint_not_a_crash(qapp, pane):
    pane.show_path(None)
    assert pane._info_line() == ""
    pane.repaint()
