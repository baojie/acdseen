"""The browsing <-> viewing page switch.

Browsing and viewing are two pages of the same window (QStackedWidget), not two
windows. While viewing, only the image remains in the window -- exactly what the
original Viewer looked like, just without opening another window, so there is no need
to fight for focus with activateWindow() on exit.

Depends on the host providing: _model _view _stack _splitter _status _loader _preview
                               _browse_actions _dir _update_status()
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView

from . import config
from .viewer import Viewer


class ViewHostMixin:
    def _open_index(self, index: QModelIndex) -> None:
        """Double-click / Enter. Clicking on ".." goes to the parent, not to the viewer."""
        if self._model.is_parent_row(index):
            self._go_parent()
            return
        row = self._model.image_index(index)
        if row >= 0:
            self._open_viewer(row)

    def _open_current(self) -> None:
        idx = self._view.currentIndex()
        if idx.isValid():
            self._open_index(idx)

    def _start_slideshow(self, start: int = 0) -> None:
        """Start a fullscreen slideshow from image number start. start is the image
        index, not the view row -- with a ".." row they differ by 1, and using the
        wrong one would always start from the second image."""
        n = self._model.image_count()
        if n == 0:
            return
        v = self._open_viewer(max(0, min(start, n - 1)))
        if v:
            self.showFullScreen()
            v.toggle_slideshow()

    def is_viewing(self) -> bool:
        return self._viewer is not None

    def _open_viewer(self, index: int) -> Viewer | None:
        """Switch to the viewing page. Same window, no new window."""
        files = self._model.paths()
        if not files:
            return None
        if self._viewer is not None:
            self._close_viewer()

        self._loader.set_paused(True)          # yield the CPU to the viewer
        self._preview.set_paused(True)
        v = Viewer(files, index)
        v.exit_view.connect(self._on_exit_view)
        v.file_deleted.connect(lambda p: self._model.remove_paths({p}))
        self._viewer = v

        self._stack.addWidget(v)
        self._stack.setCurrentWidget(v)
        # The browser's Del / Enter / F5 shortcuts would steal keys from the viewer, so disable them first
        for a in self._browse_actions:
            a.setEnabled(False)
        self._status.hide()                     # while viewing, info goes through the OSD; the status bar is redundant
        v.setFocus(Qt.OtherFocusReason)
        return v

    def _on_exit_view(self, path: Path | None) -> None:
        self._close_viewer()
        if path:
            row = self._model.index_of(path)
            if row >= 0:
                idx = self._model.index(row, 0)
                self._view.setCurrentIndex(idx)
                self._view.scrollTo(idx, QAbstractItemView.EnsureVisible)
        self._view.setFocus(Qt.OtherFocusReason)

    def _close_viewer(self) -> None:
        """Tear down the viewing page and return to the thumbnail page."""
        v, self._viewer = self._viewer, None
        if v is not None:
            v.teardown()
            self._stack.removeWidget(v)
            v.deleteLater()

        if self.isFullScreen():
            self.showNormal()
        self._stack.setCurrentWidget(self._splitter)
        self.menuBar().show()
        self._status.show()
        for a in self._browse_actions:
            a.setEnabled(True)
        self._loader.set_paused(False)
        self._preview.set_paused(False)
        self.setWindowTitle(f"{self._dir} — {config.APP_NAME}")
        self._update_status()

    def changeEvent(self, ev) -> None:
        """Also hide the menu bar while viewing fullscreen -- only the image should remain on screen."""
        if ev.type() == QEvent.WindowStateChange and self._viewer is not None:
            self.menuBar().setVisible(not self.isFullScreen())
        super().changeEvent(ev)
