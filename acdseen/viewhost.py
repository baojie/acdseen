"""浏览 ↔ 看图 的页面切换。

浏览和看图是同一个窗口的两页（QStackedWidget），不是两个窗口。看图时窗口里
只剩那张图 —— 这正是原版 Viewer 的样子，只是不再另开窗，也就不必在退出时
靠 activateWindow() 抢焦点。

依赖宿主提供：_model _view _stack _splitter _status _loader _preview
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
        path = self._model.path_at(index)
        if path:
            self._open_viewer(self._model.index_of(path))

    def _open_current(self) -> None:
        idx = self._view.currentIndex()
        if idx.isValid():
            self._open_index(idx)

    def _start_slideshow(self, start: int = 0) -> None:
        """从第 start 张开始全屏幻灯演示。"""
        if self._model.rowCount() == 0:
            return
        v = self._open_viewer(max(0, min(start, self._model.rowCount() - 1)))
        if v:
            self.showFullScreen()
            v.toggle_slideshow()

    def is_viewing(self) -> bool:
        return self._viewer is not None

    def _open_viewer(self, index: int) -> Viewer | None:
        """切到看图页。同一个窗口，不开新窗。"""
        files = self._model.paths()
        if not files:
            return None
        if self._viewer is not None:
            self._close_viewer()

        self._loader.set_paused(True)          # 把 CPU 让给看图器
        self._preview.set_paused(True)
        v = Viewer(files, index)
        v.exit_view.connect(self._on_exit_view)
        v.file_deleted.connect(lambda p: self._model.remove_paths({p}))
        self._viewer = v

        self._stack.addWidget(v)
        self._stack.setCurrentWidget(v)
        # 浏览器的 Del / Enter / F5 等快捷键会抢走看图器的按键，先关掉
        for a in self._browse_actions:
            a.setEnabled(False)
        self._status.hide()                     # 看图时信息走 OSD，状态栏是多余的
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
        """拆掉看图页，回到缩略图页。"""
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
        """全屏看图时把菜单栏也收掉 —— 屏幕上只该剩那张图。"""
        if ev.type() == QEvent.WindowStateChange and self._viewer is not None:
            self.menuBar().setVisible(not self.isFullScreen())
        super().changeEvent(ev)
