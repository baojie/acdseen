"""A fullscreen image viewer -- a clone of the ACDSee Image Viewer.

The soul of the original: open and you see the image, paging has no delay, hands never
leave the keyboard, and the screen shows nothing but the image.
So there is no toolbar and no sidebar here; all information goes through a toggleable
OSD overlay.

This file keeps only the view body: navigation, load callbacks, zoom, keyboard/mouse
events, delete.
The rest is split out by feature:
  slideshow.py  slideshow interval and shuffled playback
  render.py     paintEvent and the OSD overlay
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QMenu, QMessageBox, QWidget

from . import config
from .i18n import tr
from .loader import ImageLoader
from .render import RenderMixin
from .slideshow import SlideshowMixin

# FIT_WINDOW is the original behavior: small images are not enlarged; a 200px image
# stays 200px in fullscreen.
# FIT_FILL is "really fill": small images are also scaled up to hug the short edge of
# the display area.
FIT_WINDOW, FIT_WIDTH, FIT_ONE_TO_ONE, FIT_FREE, FIT_FILL = range(5)

FIT_NAMES = {
    FIT_WINDOW: "fit.window",
    FIT_WIDTH: "fit.width",
    FIT_ONE_TO_ONE: "fit.1to1",
    FIT_FILL: "fit.fill",
}


class Viewer(SlideshowMixin, RenderMixin, QWidget):
    """The viewing view. Holds a file list and moves forward and back through it itself.

    Can be a standalone window (`acdseen photo.jpg` opens an image directly), or be
    embedded as a page of the browser's QStackedWidget. The only difference is who
    responds to exit_view: standalone means quit the program, embedded means switch
    back to the thumbnail page.
    """

    exit_view = Signal(object)       # requests leaving the view, carrying the current path
    closed = Signal(object)          # the window was really closed (standalone mode only)
    file_deleted = Signal(object)

    def __init__(self, files: list[Path], index: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(config.APP_NAME)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)

        self._files = list(files)
        self._index = max(0, min(index, len(self._files) - 1))

        self._image: QImage | None = None
        self._pixmap: QPixmap | None = None
        self._is_preview = False          # whether what's shown is the first low-res image
        self._error: str | None = None

        # Default to filling the display area: single-page viewing and slideshow should
        # both fill the window, with small images scaled up too.
        # For the original "small images not enlarged" behavior, press * to switch to FIT_WINDOW.
        self._fit_mode = FIT_FILL
        self._base_fit = FIT_FILL     # the mode to return to when paging after a manual zoom
        self._prev_fit = FIT_FILL     # the mode to return to when middle-click switches back from 1:1
        self._scale = 1.0
        self._offset = QPoint(0, 0)       # translation of the image relative to the viewport center
        self._drag_from: QPoint | None = None
        self._drag_offset = QPoint(0, 0)

        # Cache of the scaled bitmap, to avoid resampling the big image every frame
        self._scaled: QPixmap | None = None
        self._scaled_for: tuple[float, int, int] | None = None

        self._show_osd = True
        self._osd_timer = QTimer(self)
        self._osd_timer.setSingleShot(True)
        self._osd_timer.timeout.connect(self._hide_transient_osd)
        self._transient: str | None = None

        self._slideshow = QTimer(self)
        self._slideshow.timeout.connect(self._slideshow_tick)
        self._slideshow_delay: float = config.DEFAULT_SLIDESHOW_DELAY
        self._shuffle = False
        self._original_files = list(files)   # restore to this when shuffle is turned off

        self._loader = ImageLoader(self)
        self._loader.preview_ready.connect(self._on_preview)
        self._loader.full_ready.connect(self._on_full)
        self._loader.load_failed.connect(self._on_failed)

        self.resize(1000, 720)
        self._goto(self._index, initial=True)

    # ------------------------------------------------------------- Properties
    @property
    def current(self) -> Path | None:
        if 0 <= self._index < len(self._files):
            return self._files[self._index]
        return None

    # ------------------------------------------------------------- Navigation
    def _goto(self, index: int, initial: bool = False) -> None:
        if not self._files:
            self.exit_view.emit(None)
            return
        self._index = index % len(self._files)
        path = self._files[self._index]

        self._error = None
        self._invalidate_scaled()

        img = self._loader.load(path)
        if img is not None:
            # Cache hit: this frame is full resolution, paging with zero delay
            self._set_image(img, preview=False)
        else:
            # Miss: keep the previous frame and swap when the preview signal arrives.
            # Key point -- never clear the screen, never show "loading".
            self._is_preview = True

        self._update_title()
        self._queue_read_ahead()
        if not initial:
            self.update()

    def _queue_read_ahead(self) -> None:
        n = len(self._files)
        if n <= 1:
            return
        neighbours = []
        for d in range(1, config.READ_AHEAD + 1):
            neighbours.append(self._files[(self._index + d) % n])
            neighbours.append(self._files[(self._index - d) % n])
        self._loader.read_ahead(neighbours)

    def next_image(self) -> None:
        # Once a shuffled round is finished, reshuffle; otherwise the second round repeats the same order, which defeats shuffling
        if self._shuffle and self._index + 1 >= len(self._files):
            self._reshuffle()
            self._goto(0)
            return
        self._goto(self._index + 1)

    def prev_image(self) -> None:
        self._goto(self._index - 1)

    def first_image(self) -> None:
        self._goto(0)

    def last_image(self) -> None:
        self._goto(len(self._files) - 1)

    # ------------------------------------------------------------- Load callbacks
    def _on_preview(self, path: Path, img: QImage) -> None:
        if path == self.current:
            self._set_image(img, preview=True)

    def _on_full(self, path: Path, img: QImage) -> None:
        if path == self.current:
            # Seamless replacement: only "fit" zoom modes need recomputation; position is preserved at 1:1
            self._set_image(img, preview=False, keep_view=True)

    def _on_failed(self, path: Path) -> None:
        if path == self.current:
            self._image = self._pixmap = self._scaled = None
            self._error = tr("err.decode", path.name)
            self.update()

    def _set_image(self, img: QImage, preview: bool, keep_view: bool = False) -> None:
        was_preview = self._is_preview
        self._image = img
        self._pixmap = QPixmap.fromImage(img)
        self._is_preview = preview
        self._invalidate_scaled()

        # When swapping from preview to full resolution, keep the view parameters (zoom mode, pan)
        if not (keep_view and not was_preview):
            if not keep_view:
                self._offset = QPoint(0, 0)
                if self._fit_mode == FIT_FREE:
                    self._fit_mode = self._base_fit
        self.update()

    # ------------------------------------------------------------- Zoom
    def _fitted_scale(self) -> float:
        if not self._image:
            return 1.0
        iw, ih = self._image.width(), self._image.height()
        if iw <= 0 or ih <= 0:
            return 1.0
        vw, vh = self.width(), self.height()
        if self._fit_mode == FIT_WINDOW:
            s = min(vw / iw, vh / ih)
            return min(s, 1.0)      # small images are not enlarged -- original behavior
        if self._fit_mode == FIT_FILL:
            # Scale up when it should be: the whole image hugs the display area, keeping aspect ratio
            return min(vw / iw, vh / ih)
        if self._fit_mode == FIT_WIDTH:
            return vw / iw
        return 1.0

    def _effective_scale(self) -> float:
        if self._fit_mode == FIT_FREE:
            return self._scale
        return self._fitted_scale()

    def _set_fit(self, mode: int) -> None:
        self._fit_mode = mode
        if mode != FIT_FREE:
            # Remember this mode: return to it when flipping to the next image, rather
            # than always falling back to fit-window.
            # If "fit to display" is chosen during a slideshow, every image should fill it.
            self._base_fit = mode
        self._offset = QPoint(0, 0)
        self._invalidate_scaled()
        self._flash(tr(FIT_NAMES.get(mode, "")))
        self.update()

    def zoom_by(self, direction: int, anchor: QPoint | None = None) -> None:
        cur = self._effective_scale()
        steps = config.ZOOM_STEPS
        if direction > 0:
            nxt = next((s for s in steps if s > cur * 1.001), steps[-1])
        else:
            nxt = next((s for s in reversed(steps) if s < cur * 0.999), steps[0])

        # Zoom anchored at the mouse position (or viewport center)
        if anchor is not None and self._image:
            centre = QPoint(self.width() // 2, self.height() // 2)
            rel = anchor - centre - self._offset
            self._offset = self._offset - rel * (nxt / cur - 1.0)

        self._scale = nxt
        self._fit_mode = FIT_FREE
        self._invalidate_scaled()
        self._flash(f"{nxt * 100:.0f}%")
        self.update()

    def _invalidate_scaled(self) -> None:
        self._scaled = None
        self._scaled_for = None

    # ------------------------------------------------------------- File operations
    def delete_current(self) -> None:
        path = self.current
        if path is None:
            return
        if QMessageBox.question(
            self, tr("action.delete"), tr("msg.delete_confirm", path.name),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        try:
            path.unlink()
        except OSError as e:
            QMessageBox.warning(self, tr("msg.delete_failed"), str(e))
            return

        self._loader.drop(path)
        self.file_deleted.emit(path)
        del self._files[self._index]
        if not self._files:
            self.exit_view.emit(None)   # all deleted; nothing left to look at
            return
        self._goto(min(self._index, len(self._files) - 1))

    # ------------------------------------------------------------- Input
    def keyPressEvent(self, ev) -> None:
        k = ev.key()
        mods = ev.modifiers()

        if k in (Qt.Key_Space, Qt.Key_PageDown, Qt.Key_Right, Qt.Key_Down, Qt.Key_N):
            if self._fit_mode == FIT_FREE and k in (Qt.Key_Right, Qt.Key_Down):
                self._pan(-60 if k == Qt.Key_Right else 0, -60 if k == Qt.Key_Down else 0)
            else:
                self.next_image()
        elif k in (Qt.Key_Backspace, Qt.Key_PageUp, Qt.Key_Left, Qt.Key_Up, Qt.Key_P):
            if self._fit_mode == FIT_FREE and k in (Qt.Key_Left, Qt.Key_Up):
                self._pan(60 if k == Qt.Key_Left else 0, 60 if k == Qt.Key_Up else 0)
            else:
                self.prev_image()
        elif k == Qt.Key_Home:
            self.first_image()
        elif k == Qt.Key_End:
            self.last_image()
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_by(+1)
        elif k in (Qt.Key_Minus, Qt.Key_Underscore):
            self.zoom_by(-1)
        elif k == Qt.Key_Asterisk:
            self._set_fit(FIT_WINDOW)
        elif k == Qt.Key_Slash:
            self._set_fit(FIT_ONE_TO_ONE)
        elif k == Qt.Key_W:
            self._set_fit(FIT_WIDTH)
        elif k == Qt.Key_Z:
            self._set_fit(FIT_FILL)
        elif k in (Qt.Key_F, Qt.Key_Return, Qt.Key_Enter, Qt.Key_F11):
            self.toggle_fullscreen()
        elif k == Qt.Key_S:
            self.toggle_slideshow()
        elif k == Qt.Key_R:
            self.toggle_shuffle()
        elif k == Qt.Key_D:
            self.ask_delay()
        elif k == Qt.Key_BracketRight:
            self._cycle_delay(+1)
        elif k == Qt.Key_BracketLeft:
            self._cycle_delay(-1)
        elif k == Qt.Key_I:
            self._show_osd = not self._show_osd
            self.update()
        elif k == Qt.Key_Delete:
            self.delete_current()
        elif k == Qt.Key_Escape:
            if self.window().isFullScreen():
                self.window().showNormal()
            else:
                self.exit_view.emit(self.current)
        else:
            super().keyPressEvent(ev)

    def _pan(self, dx: int, dy: int) -> None:
        self._offset += QPoint(dx, dy)
        self.update()

    def toggle_fullscreen(self) -> None:
        # Applies to the top-level window: the main window when embedded in the browser, itself when standalone
        win = self.window()
        win.showNormal() if win.isFullScreen() else win.showFullScreen()
        self._invalidate_scaled()

    def is_fullscreen(self) -> bool:
        return self.window().isFullScreen()

    def wheelEvent(self, ev) -> None:
        delta = ev.angleDelta().y()
        if ev.modifiers() & Qt.ControlModifier:
            self.zoom_by(1 if delta > 0 else -1, ev.position().toPoint())
        elif self._fit_mode == FIT_FREE:
            self._pan(0, 60 if delta > 0 else -60)
        else:
            self.prev_image() if delta > 0 else self.next_image()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            self._drag_from = ev.position().toPoint()
            self._drag_offset = QPoint(self._offset)
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, ev) -> None:
        if self._drag_from is not None:
            moved = ev.position().toPoint() - self._drag_from
            if self._fit_mode != FIT_FREE and moved.manhattanLength() > 3:
                # Dragging automatically switches to free zoom; otherwise dragging would do nothing, which is confusing
                self._scale = self._effective_scale()
                self._fit_mode = FIT_FREE
            self._offset = self._drag_offset + moved
            self.update()

    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            moved = (ev.position().toPoint() - (self._drag_from or QPoint())).manhattanLength()
            self._drag_from = None
            self.setCursor(Qt.ArrowCursor)
            if moved <= 3:
                self.next_image()   # single click pages
        elif ev.button() == Qt.MiddleButton:
            # Toggle between "your chosen fit mode" and 1:1. Can't just read _base_fit --
            # it also becomes 1:1 when switching to 1:1, so you could never switch back.
            if self._fit_mode == FIT_ONE_TO_ONE:
                self._set_fit(self._prev_fit)
            else:
                self._prev_fit = self._base_fit
                self._set_fit(FIT_ONE_TO_ONE)

    def mouseDoubleClickEvent(self, ev) -> None:
        self.toggle_fullscreen()

    def contextMenuEvent(self, ev) -> None:
        m = QMenu(self)
        m.addAction(tr("viewer.next"), self.next_image)
        m.addAction(tr("viewer.prev"), self.prev_image)
        m.addSeparator()
        m.addAction(tr("viewer.fit_window"), lambda: self._set_fit(FIT_WINDOW))
        m.addAction(tr("viewer.fit_fill"), lambda: self._set_fit(FIT_FILL))
        m.addAction(tr("viewer.fit_width"), lambda: self._set_fit(FIT_WIDTH))
        m.addAction(tr("viewer.actual"), lambda: self._set_fit(FIT_ONE_TO_ONE))
        m.addAction(tr("viewer.fullscreen"), self.toggle_fullscreen)
        m.addSeparator()
        act = m.addAction(tr("viewer.slideshow"), self.toggle_slideshow)
        act.setCheckable(True); act.setChecked(self._slideshow.isActive())
        act = m.addAction(tr("viewer.shuffle"), self.toggle_shuffle)
        act.setCheckable(True); act.setChecked(self._shuffle)
        m.addAction(tr("viewer.delay", self.format_delay(self._slideshow_delay)),
                    self.ask_delay)
        m.addSeparator()
        m.addAction(tr("viewer.delete"), self.delete_current)
        m.addAction(tr("viewer.back"), lambda: self.exit_view.emit(self.current))
        m.exec(ev.globalPos())

    def teardown(self) -> None:
        """Stop the timers and the decode thread. The host must call this before discarding the view."""
        self._slideshow.stop()
        self._loader.shutdown()

    def closeEvent(self, ev) -> None:
        self.teardown()
        self.closed.emit(self.current)
        super().closeEvent(ev)
