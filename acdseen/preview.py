"""The preview pane at the bottom-left of the browser -- a large preview of the currently selected image.

In the original ACDSee 1.x, the Preview Pane could be configured to the left / bottom /
right positions; the default layout of the Mac 1.5.1 build is bottom-left: directory
tree on top, preview below.

The approach is the same as the thumbnails: background-thread decoding + generation
invalidation. But only one thread is opened, and only one image is looked at at a time;
it never steals CPU from the viewer.

The decode target follows the pane size (original behavior: the preview reloads
automatically whenever the preview area is resized), and resize uses a single-shot
QTimer for debouncing, so dragging the splitter doesn't trigger a decoding frenzy.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (QObject, QRunnable, QRect, QThreadPool, QTimer,
                            Qt, Signal, Slot)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QImage, QPainter,
                           QPalette)
from PySide6.QtWidgets import QWidget

from .i18n import tr
from .loader import image_dimensions, load_image
from .util import format_size, human_dims

# Margin added to the pane size: make the target edge slightly larger so scaling doesn't have to be so exact
_EDGE_MARGIN = 40


class _PreviewSignals(QObject):
    ready = Signal(object, object, int)   # path, QImage | None, generation


class _PreviewTask(QRunnable):
    """Decode one preview image. edge is given by the pane size; the decoder directly produces a downscaled version (fast)."""

    def __init__(self, path: Path, edge: int, signals: _PreviewSignals,
                 generation: int, current_gen):
        super().__init__()
        self.path, self.edge = path, edge
        self.signals = signals
        self.generation, self._current_gen = generation, current_gen
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        if self.generation != self._current_gen():
            return
        img = load_image(self.path, max_edge=self.edge)
        if self.generation == self._current_gen():
            self.signals.ready.emit(self.path, img, self.generation)


class PreviewPane(QWidget):
    """Preview of the currently selected image. The image is centered and not enlarged; the bottom line shows the filename and dimensions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setAttribute(Qt.WA_OpaquePaintEvent)   # repaint the whole frame every time, no flicker

        self._path: Path | None = None
        self._img: QImage | None = None
        self._dims: tuple[int, int] | None = None   # the original image's dimensions, not the preview's
        self._error = False
        self._generation = 0
        self._paused = False

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)             # only one image at a time for the preview
        self._signals = _PreviewSignals()
        self._signals.ready.connect(self._on_ready)

        # resize debounce: re-decode only after the size has been stable for 200ms
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._reload_current)

    def _gen(self) -> int:
        return self._generation

    # ------------------------------------------------------------- Public interface
    def show_path(self, path: Path | None) -> None:
        """Switch to the newly selected item. None means nothing is selected (empty directory)."""
        if path == self._path:
            return
        self._path = path
        # Read only the file header, don't decode pixels -- the info line must report
        # the original dimensions, and self._img is scaled to the pane size, so its
        # dimensions would report wrong numbers.
        self._dims = image_dimensions(path) if path is not None else None
        self._invalidate()
        self._request()
        self.update()

    def clear(self) -> None:
        self.show_path(None)

    def set_paused(self, paused: bool) -> None:
        """Yield when the viewer opens: invalidate in-flight tasks; reload the current
        item when it closes.

        Must be a persistent state, not a one-shot invalidation -- switching to the
        viewing page makes this pane receive a resizeEvent, and after 200ms the
        debounce timer would kick decoding back up, right when the viewer needs the CPU
        most."""
        if paused == self._paused:
            return
        self._paused = paused
        self._resize_timer.stop()
        self._invalidate()
        if not paused:
            self._request()
        self.update()

    def shutdown(self) -> None:
        """Call before the host is destroyed: stop the debounce timer, invalidate, and wait for the decode thread to finish."""
        self._paused = True      # resizes can still arrive while closing; don't start new decodes
        self._resize_timer.stop()
        self._invalidate()
        self._pool.waitForDone(1000)

    # ------------------------------------------------------------- Loading
    def _need_edge(self) -> int:
        return max(96, self.width(), self.height()) + _EDGE_MARGIN

    def _invalidate(self) -> None:
        self._generation += 1
        self._pool.clear()
        self._img = None
        self._error = False

    def _request(self) -> None:
        if self._path is None or self._paused:
            return
        self._pool.start(_PreviewTask(self._path, self._need_edge(),
                                      self._signals, self._generation, self._gen))

    def _reload_current(self) -> None:
        if self._path is not None:
            self._invalidate()
            self._request()

    def _on_ready(self, path: Path, img: QImage | None, generation: int) -> None:
        if generation != self._generation or path != self._path:
            return
        if img is None or img.isNull():
            self._error = True
        else:
            self._img = img
        self.update()

    # ------------------------------------------------------------- Painting
    def paintEvent(self, ev) -> None:
        # All colors go through the palette -- so when the Win95 look is applied the
        # pane turns grayish-white with it, leaving no jarring black block in the gray
        pal = self.palette()
        p = QPainter(self)
        p.fillRect(self.rect(), pal.base())
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self._paint_sunken_frame(p, pal)

        info_h = self._info_height()
        img_area = QRect(2, 2, self.width() - 4, self.height() - info_h - 2)

        if self._path is None:
            self._paint_hint(p, tr("preview.hint"), img_area)
        elif self._error:
            self._paint_hint(p, tr("err.decode", self._path.name), img_area)
        elif self._img is not None:
            self._paint_image(p, self._img, img_area)
        else:
            self._paint_hint(p, tr("preview.decoding"), img_area)

        self._paint_info(p, self._info_line())

    def _paint_image(self, p: QPainter, img: QImage, area: QRect) -> None:
        iw, ih = img.width(), img.height()
        if iw <= 0 or ih <= 0:
            return
        s = min(area.width() / iw, area.height() / ih, 1.0)   # not enlarged -- original behavior
        w, h = max(1, int(iw * s)), max(1, int(ih * s))
        x = area.x() + (area.width() - w) // 2
        y = area.y() + (area.height() - h) // 2
        p.drawImage(QRect(x, y, w, h), img)

    def _paint_hint(self, p: QPainter, text: str, area: QRect) -> None:
        f = QFont(); f.setPointSize(10); p.setFont(f)
        p.setPen(self.palette().color(QPalette.Disabled, QPalette.Text))
        p.drawText(area, Qt.AlignCenter, text)

    def _paint_sunken_frame(self, p: QPainter, pal) -> None:
        """The Win95 sunken bevel: dark top-left, light bottom-right. These colors also follow the dark theme automatically."""
        w, h = self.width(), self.height()
        p.save()
        p.setPen(pal.color(QPalette.Shadow))
        p.drawLine(0, 0, w - 1, 0); p.drawLine(0, 0, 0, h - 1)
        p.setPen(pal.color(QPalette.Light))
        p.drawLine(0, h - 1, w - 1, h - 1); p.drawLine(w - 1, 0, w - 1, h - 1)
        p.restore()

    def _info_line(self) -> str:
        if self._path is None:
            return ""
        path = self._path
        parts = [path.name]
        if self._dims:
            parts.append(human_dims(*self._dims))
        try:
            st = path.stat()
            parts.append(format_size(st.st_size))
        except OSError:
            pass
        return "   ".join(parts)

    def _info_height(self) -> int:
        f = QFont(); f.setPointSize(10)
        return QFontMetrics(f).height() + 12

    def _paint_info(self, p: QPainter, text: str) -> None:
        if not text:
            return
        f = QFont(); f.setPointSize(10); p.setFont(f)
        fm = QFontMetrics(f)
        h = self._info_height()
        pal = self.palette()
        bar = QRect(2, self.height() - h - 2, self.width() - 4, h)
        p.fillRect(bar, pal.window())
        p.setPen(pal.color(QPalette.WindowText))
        p.drawText(bar.adjusted(8, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft,
                   fm.elidedText(text, Qt.ElideMiddle, bar.width() - 16))

    def resizeEvent(self, ev) -> None:
        if not self._paused:
            self._resize_timer.start(200)
        super().resizeEvent(ev)
