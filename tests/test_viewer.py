"""Viewer: navigation, zoom modes, slideshow, fault tolerance."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from acdseen import config
from acdseen.i18n import tr
from acdseen.util import list_images
from acdseen.viewer import (FIT_FILL, FIT_FREE, FIT_ONE_TO_ONE, FIT_WIDTH, FIT_WINDOW,
                            Viewer)
from conftest import pump


def press(w, key, mods=Qt.NoModifier):
    QApplication.sendEvent(w, QKeyEvent(QKeyEvent.KeyPress, key, mods))


@pytest.fixture
def viewer(qapp, pics):
    files = [f for f in list_images(pics) if f.name != "broken.jpg"]
    v = Viewer(files, 0)
    v.resize(1000, 700)
    v.show()
    pump(qapp, 5000, lambda: v._image is not None)
    yield v
    v.close()
    pump(qapp, 200)


def test_first_image_decodes(viewer):
    assert viewer._image is not None
    assert viewer._error is None


def test_space_pages_forward(qapp, viewer):
    first = viewer.current
    press(viewer, Qt.Key_Space)
    pump(qapp, 3000, lambda: viewer._image is not None)
    assert viewer.current != first


def test_backspace_pages_back(qapp, viewer):
    press(viewer, Qt.Key_Space)
    pump(qapp, 2000)
    press(viewer, Qt.Key_Backspace)
    pump(qapp, 2000)
    assert viewer._index == 0


def test_paging_wraps_around(qapp, viewer):
    n = len(viewer._files)
    for _ in range(n):
        press(viewer, Qt.Key_Space)
        pump(qapp, 400)
    assert viewer._index == 0, "a full loop should come back to the start"


def test_home_and_end(qapp, viewer):
    press(viewer, Qt.Key_End)
    pump(qapp, 2000)
    assert viewer._index == len(viewer._files) - 1
    press(viewer, Qt.Key_Home)
    pump(qapp, 2000)
    assert viewer._index == 0


def test_paging_does_not_blank_the_screen(qapp, viewer):
    """Core feel: when switching to an uncached image, the old frame must stay on screen until the new one decodes."""
    before = viewer._image
    assert before is not None

    # Clear the LRU to guarantee the target image isn't cached -- otherwise read-ahead would hit synchronously and this path wouldn't be exercised
    viewer._loader._lru.clear()
    viewer._goto(len(viewer._files) - 1)

    assert viewer._image is before, "the screen was blanked between images, which shows up as a flicker"
    assert pump(qapp, 5000, lambda: viewer._image is not before), "the new image never finished decoding"


def test_prefetch_hit_swaps_synchronously(qapp, viewer):
    """The flip side of a read-ahead hit: don't keep the old image, show the already-cached new one immediately."""
    target = viewer._files[1]
    assert pump(qapp, 6000, lambda: viewer._loader.cached(target) is not None)
    before = viewer._image
    viewer._goto(1)
    assert viewer._image is not before
    assert not viewer._is_preview, "a cache hit must yield full resolution, not the preview"


def test_small_images_fill_the_box_by_default(qapp, pics):
    """Single-page viewing and slideshow should both fill the window without pressing Z first."""
    small = pics / "IMG_003.gif"           # 320x240
    v = Viewer([small], 0)
    v.resize(1600, 1200)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    assert v._fit_mode == FIT_FILL, "scale-to-box is meant to be the default"
    assert v._effective_scale() > 1.0, "small images must be enlarged by default"
    v.close()


def test_asterisk_returns_to_the_original_no_upscale(qapp, pics):
    """* keeps ACDSee's original behavior: small images stay at their original size."""
    small = pics / "IMG_003.gif"           # 320x240
    v = Viewer([small], 0)
    v.resize(1600, 1200)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    v._set_fit(FIT_WINDOW)
    assert v._effective_scale() == 1.0
    v.close()


def test_fit_window_shrinks_large_images(qapp, pics):
    v = Viewer([pics / "IMG_002.bmp"], 0)  # 2400x1800
    v.resize(800, 600)
    v.show()
    pump(qapp, 5000, lambda: v._image is not None and not v._is_preview)
    assert v._effective_scale() < 1.0
    v.close()


def test_zoom_steps(qapp, viewer):
    viewer._set_fit(FIT_ONE_TO_ONE)
    assert viewer._effective_scale() == 1.0
    viewer.zoom_by(+1)
    assert viewer._fit_mode == FIT_FREE
    assert viewer._effective_scale() > 1.0
    viewer.zoom_by(-1)
    assert viewer._effective_scale() == pytest.approx(1.0)


def test_zoom_stays_in_range(qapp, viewer):
    for _ in range(40):
        viewer.zoom_by(+1)
    assert viewer._effective_scale() == config.ZOOM_STEPS[-1]
    for _ in range(80):
        viewer.zoom_by(-1)
    assert viewer._effective_scale() == config.ZOOM_STEPS[0]


def test_zoom_mode_shortcuts(qapp, viewer):
    press(viewer, Qt.Key_Slash)
    assert viewer._fit_mode == FIT_ONE_TO_ONE
    press(viewer, Qt.Key_W)
    assert viewer._fit_mode == FIT_WIDTH
    press(viewer, Qt.Key_Asterisk)
    assert viewer._fit_mode == FIT_WINDOW


def test_arrows_pan_when_zoomed_freely(qapp, viewer):
    viewer.zoom_by(+1)
    idx, off = viewer._index, viewer._offset.x()
    press(viewer, Qt.Key_Right)
    assert viewer._index == idx, "while zoomed, arrows pan rather than page"
    assert viewer._offset.x() != off


def test_arrows_page_in_fit_mode(qapp, viewer):
    viewer._set_fit(FIT_WINDOW)
    press(viewer, Qt.Key_Right)
    pump(qapp, 1500)
    assert viewer._index == 1


def test_slideshow_toggle(qapp, viewer):
    assert not viewer._slideshow.isActive()
    press(viewer, Qt.Key_S)
    assert viewer._slideshow.isActive()
    press(viewer, Qt.Key_S)
    assert not viewer._slideshow.isActive()


def test_slideshow_interval_is_adjustable(qapp, viewer):
    base = viewer._slideshow_delay
    viewer._cycle_delay(+1)
    assert viewer._slideshow_delay > base
    viewer._cycle_delay(-1)
    assert viewer._slideshow_delay == base


def test_info_bar_toggle(qapp, viewer):
    on = viewer._show_osd
    press(viewer, Qt.Key_I)
    assert viewer._show_osd is not on


def test_prefetch_fills_after_paging(qapp, viewer):
    pump(qapp, 6000, lambda: len(viewer._loader._lru) >= 2)
    assert len(viewer._loader._lru) >= 2, "prefetch did not run, so paging will stall"


def test_broken_file_marks_error_not_crash(qapp, pics):
    v = Viewer([pics / "broken.jpg"], 0)
    v.show()
    assert pump(qapp, 5000, lambda: v._error is not None)
    assert v._image is None
    v.repaint()          # error state must be drawable too
    v.close()


def test_delete_advances_to_the_next_image(qapp, workdir, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    files = [f for f in list_images(workdir) if f.name != "broken.jpg"]
    n = len(files)
    v = Viewer(files, 0)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)

    doomed = v.current
    v.delete_current()
    pump(qapp, 2000)

    assert not doomed.exists()
    assert len(v._files) == n - 1
    assert v.current != doomed
    v.close()


def test_deleting_the_last_image_requests_exit(qapp, tmp_path, pics, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    lone = tmp_path / "only.png"
    lone.write_bytes((pics / "IMG_001.png").read_bytes())

    v = Viewer([lone], 0)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)

    exits = []
    v.exit_view.connect(lambda p: exits.append(p))
    v.delete_current()
    pump(qapp, 500)

    assert not lone.exists()
    assert exits == [None], "with nothing left it must request exit, or it sits on a blank page"
    v.close()


def test_esc_requests_exit_instead_of_closing_itself(qapp, viewer):
    """The viewer doesn't decide its own fate -- embedded in the browser it returns, standalone it exits."""
    exits = []
    viewer.exit_view.connect(lambda p: exits.append(p))
    press(viewer, Qt.Key_Escape)
    assert exits == [viewer.current]
    assert viewer.isVisible(), "it must not close itself unasked"


def test_esc_leaves_fullscreen_first(qapp, viewer):
    viewer.toggle_fullscreen()
    pump(qapp, 500)
    exits = []
    viewer.exit_view.connect(lambda p: exits.append(p))
    press(viewer, Qt.Key_Escape)
    pump(qapp, 500)
    assert not exits, "the first Esc should only leave full screen"
    assert not viewer.is_fullscreen()


def test_fullscreen_toggle(qapp, viewer):
    viewer.toggle_fullscreen()
    pump(qapp, 300)
    assert viewer.is_fullscreen()
    viewer.toggle_fullscreen()
    pump(qapp, 300)
    assert not viewer.is_fullscreen()


def test_emits_closed_when_closed(qapp, pics):
    files = [f for f in list_images(pics) if f.name != "broken.jpg"]
    v = Viewer(files, 1)
    v.show()
    pump(qapp, 3000, lambda: v._image is not None)
    seen = []
    v.closed.connect(lambda p: seen.append(p))
    expected = v.current
    v.close()
    pump(qapp, 300)
    assert seen == [expected], "the browser relies on this signal to sync its selection"


# ------------------------------------------------------------------ slideshow interval
def test_interval_accepts_any_number_of_seconds(viewer):
    viewer.set_delay(2.5)
    assert viewer._slideshow_delay == 2.5
    assert viewer._interval_ms() == 2500


def test_zero_seconds_does_not_pass_zero_to_the_timer(viewer):
    """Passing a real 0 would spin the CPU. The 0 notch uses the minimum tick and brakes by not advancing until decoded."""
    viewer.set_delay(0)
    assert viewer._slideshow_delay == 0
    assert viewer._interval_ms() == config.SLIDESHOW_ASAP_MS > 0
    assert viewer.format_delay(0) == tr("slideshow.asap")


def test_zero_second_slideshow_runs_without_skipping_frames(qapp, viewer):
    viewer.set_delay(0)
    viewer.toggle_slideshow()
    assert viewer._slideshow.isActive()
    start = viewer.current
    assert pump(qapp, 8000, lambda: viewer.current != start), "the zero-second step must actually advance"
    # Guard: must not advance while the previous image hasn't decoded
    viewer._is_preview, viewer._image = True, None
    before = viewer._index
    viewer._slideshow_tick()
    assert viewer._index == before, "advancing before the decode finishes is a skipped frame"
    viewer.toggle_slideshow()


def test_out_of_range_interval_is_clamped(viewer):
    viewer.set_delay(-5)
    assert viewer._slideshow_delay == config.SLIDESHOW_DELAY_MIN
    viewer.set_delay(99999)
    assert viewer._slideshow_delay == config.SLIDESHOW_DELAY_MAX


def test_interval_steps_include_zero(viewer):
    viewer.set_delay(config.SLIDESHOW_DELAYS[1])
    viewer._cycle_delay(-1)
    assert viewer._slideshow_delay == 0, "stepping down should reach zero seconds"
    viewer._cycle_delay(-1)
    assert viewer._slideshow_delay == 0, "already at the bottom; it must not go past it"


def test_an_arbitrary_value_snaps_to_the_nearest_step(viewer):
    """After setting 7 s via the dialog, pressing ] should snap to the nearest notch instead of jumping wildly."""
    viewer.set_delay(7)
    viewer._cycle_delay(+1)
    assert viewer._slideshow_delay in config.SLIDESHOW_DELAYS
    assert viewer._slideshow_delay == 5, "7 is nearest to 5, so it snaps to 5 first"


# ------------------------------------------------------------------ shuffle
def test_shuffle_keeps_the_current_image(viewer):
    cur = viewer.current
    viewer.set_shuffle(True)
    assert viewer._shuffle
    assert viewer.current == cur, "toggling shuffle must not replace the image you are looking at"
    assert set(viewer._files) == set(viewer._original_files), "not a single image may go missing"


def test_disabling_shuffle_restores_the_original_order(viewer):
    original = list(viewer._files)
    viewer.set_shuffle(True)
    viewer.set_shuffle(False)
    assert viewer._files == original
    assert not viewer._shuffle


def test_shuffle_actually_shuffles(qapp, pics):
    """A single shuffle could theoretically return the same order; over many shuffles at least one differs."""
    files = [f for f in list_images(pics) if f.name != "broken.jpg"]
    assert len(files) >= 5, "too few samples for this test to mean anything"
    changed = False
    for _ in range(20):
        v = Viewer(files, 0)
        v.set_shuffle(True)
        if v._files != files:
            changed = True
        v.teardown()
        if changed:
            break
    assert changed, "20 shuffles with no change at all: the randomness is not working"


def test_shuffle_reshuffles_after_a_full_pass(qapp, viewer):
    viewer.set_shuffle(True)
    viewer._index = len(viewer._files) - 1     # stand on the last image
    before = list(viewer._files)
    viewer.next_image()
    pump(qapp, 300)
    assert viewer._index == 0, "it should land on the first image of the new pass"
    assert set(viewer._files) == set(before), "reshuffling must not lose images"


def test_deleting_while_shuffled_does_not_resurrect_a_file(qapp, workdir, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    files = [f for f in list_images(workdir) if f.name != "broken.jpg"]
    v = Viewer(files, 0)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)

    v.set_shuffle(True)
    doomed = v.current
    v.delete_current()
    pump(qapp, 300)
    v.set_shuffle(False)                       # restore uses _original_files
    assert doomed not in v._files, "a deleted image must not come back when shuffle is turned off"
    assert len(v._files) == len(files) - 1
    v.close()


# ------------------------------------------------------------------ fit to display box
def _small_pic(tmp_path):
    """An image far smaller than the window, used to distinguish "fit window" from "fit to display box"."""
    from PySide6.QtGui import QImage, QColor
    p = tmp_path / "small.png"
    img = QImage(120, 90, QImage.Format_RGB888)
    img.fill(QColor(200, 60, 60))
    assert img.save(str(p))
    return p


def test_fit_window_does_not_upscale_small_images(qapp, tmp_path):
    v = Viewer([_small_pic(tmp_path)], 0)
    v.resize(1000, 700)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    v._set_fit(FIT_WINDOW)
    assert v._effective_scale() == 1.0, "original behavior: small images keep their size"
    v.close()


def test_scale_to_box_upscales_small_images(qapp, tmp_path):
    v = Viewer([_small_pic(tmp_path)], 0)
    v.resize(1000, 700)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    v._set_fit(FIT_FILL)
    s = v._effective_scale()
    assert s > 1.0, "small images must be enlarged"
    # Snug against the short edge: 120x90 in 1000x700 -> constrained by height
    assert s == pytest.approx(min(v.width() / 120, v.height() / 90))
    assert int(120 * s) <= v.width() and int(90 * s) <= v.height(), "it must not exceed the display box"
    v.close()


def test_scale_to_box_keeps_the_aspect_ratio(qapp, tmp_path):
    v = Viewer([_small_pic(tmp_path)], 0)
    v.resize(400, 900)          # tall narrow window, opposite aspect ratio to the image
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    v._set_fit(FIT_FILL)
    s = v._effective_scale()
    assert s == pytest.approx(v.width() / 120), "width should be the limiting dimension"
    assert int(90 * s) < v.height(), "leave margins vertically rather than stretching"
    v.close()


def test_both_modes_agree_on_large_images(qapp, viewer):
    """When the image is larger than the window, fit-window and fit-to-display-box compute the same value."""
    viewer._set_fit(FIT_WINDOW)
    a = viewer._effective_scale()
    viewer._set_fit(FIT_FILL)
    assert viewer._effective_scale() == pytest.approx(a)
    assert a < 1.0, "the fixture image must be larger than the window, or this test means nothing"


def test_zoom_mode_persists_across_images(qapp, viewer):
    """When fit-to-display-box is chosen during slideshow, every image should fill the box; flipping one must not revert to fit-window."""
    viewer._set_fit(FIT_FILL)
    viewer.next_image()
    pump(qapp, 4000, lambda: viewer._image is not None)
    assert viewer._fit_mode == FIT_FILL


def test_paging_after_a_manual_zoom_returns_to_the_mode(qapp, viewer):
    viewer._set_fit(FIT_FILL)
    viewer.zoom_by(+1)                 # enter FIT_FREE
    assert viewer._fit_mode == FIT_FREE
    viewer.next_image()
    pump(qapp, 4000, lambda: viewer._image is not None)
    assert viewer._fit_mode == FIT_FILL, "it should return to scale-to-box, not fall back to fit-window"


def test_middle_click_toggles_between_fit_and_1to1(qapp, viewer):
    """Regression: switching to 1:1 also changes _base_fit to 1:1, so reading it directly can never switch back."""
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent, QPointF

    def middle_click():
        ev = QMouseEvent(QEvent.MouseButtonRelease, QPointF(10, 10), QPointF(10, 10),
                         Qt.MiddleButton, Qt.MiddleButton, Qt.NoModifier)
        viewer.mouseReleaseEvent(ev)

    viewer._set_fit(FIT_WINDOW)
    middle_click()
    assert viewer._fit_mode == FIT_ONE_TO_ONE
    middle_click()
    assert viewer._fit_mode == FIT_WINDOW, "it should return to the fit mode you chose"
    middle_click()
    assert viewer._fit_mode == FIT_ONE_TO_ONE, "toggling back and forth must keep working"
