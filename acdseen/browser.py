"""A clone of ACDSee Image Browser: directory tree on the left, thumbnails on the right.

Original features deliberately kept:
  * Only view one directory; no recursion, no database, no full-disk scan
  * File operations (delete / rename / copy / move) built in, no need to switch
    back to a file manager
  * Fully reachable from the keyboard

This file keeps only the window skeleton: directory tree, split layout, directory
switching, selection, status bar, and settings persistence.
The rest is split out by feature:
  thumbmodel.py  the multi-column model (shared by both views) + thumbnail cell drawing
  viewpanes.py   the thumbnail grid / detail list views, switching and header sorting
  menus.py       menu bar, context menus, help and about
  fileops.py     file operations (rename / delete / copy / cut / paste / copy to / move to)
  viewhost.py    the browsing <-> viewing page switch
  helptext.py    the F1 shortcut table
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QDir, QEvent, QModelIndex, QSettings, Qt
from PySide6.QtWidgets import (QAbstractItemView, QFileSystemModel, QLabel,
                               QMainWindow, QSplitter, QStackedWidget,
                               QStatusBar, QTreeView)

from . import config, i18n
from .fileops import FileOpsMixin
from .i18n import tr
from .loader import ThumbnailLoader, image_dimensions
from .menus import MenuMixin
from .preview import PreviewPane
from .thumbmodel import COL_NAME
from .util import format_mtime, format_size, human_dims, list_images
from .viewer import Viewer
from .viewhost import ViewHostMixin
from .viewpanes import ViewPanesMixin


class Browser(ViewPanesMixin, MenuMixin, ViewHostMixin, FileOpsMixin,
              QMainWindow):
    def __init__(self, start_dir: Path):
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self._settings = QSettings(config.ORG_NAME, config.APP_NAME)
        self._dir = start_dir
        self._sort_key = config.SORT_NAME
        self._sort_reverse = False
        self._sort_seed = 0          # only meaningful for the "random" sort, see util.list_images
        self._clipboard: tuple[str, list[Path]] | None = None   # ("copy"|"cut", paths)
        self._viewer: Viewer | None = None
        self._view_mode = config.VIEW_THUMBS
        self._thumb_edge = config.DEFAULT_THUMB_SIZE   # edge length used in icon mode; list mode does not override it

        self._loader = ThumbnailLoader(self)
        self._build_ui()
        self._build_menu()
        self._restore_state()
        # The icon provider must be set unconditionally once: the look toggle has a
        # default value, so relying only on "applied only if stored in settings" would
        # leave first launch in a half-baked state where the theme is on but the
        # directory tree icons are not swapped.
        # Here we only touch our own QFileSystemModel and leave the global style alone --
        # changing app-level styles belongs to the entry point and manual user toggling,
        # and mutating the app style while the window is being constructed has too many
        # side effects.
        self._sync_icon_provider()
        self.set_directory(start_dir)

    # ------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        self._splitter = QSplitter(Qt.Horizontal, self)

        # Left: directory tree
        self._fs = QFileSystemModel(self)
        self._fs.setRootPath("")
        self._fs.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Drives)
        self._tree = QTreeView()
        self._tree.setModel(self._fs)
        for col in range(1, self._fs.columnCount()):
            self._tree.hideColumn(col)
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(False)          # animations only slow perceived speed
        self._tree.setExpandsOnDoubleClick(True)
        self._tree.selectionModel().currentChanged.connect(self._on_tree_changed)

        self._build_views()

        # Left column: directory tree + preview pane (the original preview pane sat bottom-left)
        self._preview = PreviewPane()
        self._left_splitter = QSplitter(Qt.Vertical)
        self._left_splitter.addWidget(self._tree)
        self._left_splitter.addWidget(self._preview)
        self._left_splitter.setStretchFactor(0, 1)
        self._left_splitter.setStretchFactor(1, 0)
        self._left_splitter.setSizes([400, 220])

        self._splitter.addWidget(self._left_splitter)
        self._splitter.addWidget(self._right_pane)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([260, 900])

        # Browsing / viewing are two pages of the same window, not two windows.
        # While viewing, only the image remains in the window -- exactly what the
        # original Viewer looked like, just without opening a separate window.
        self._stack = QStackedWidget()
        self._stack.addWidget(self._splitter)
        self.setCentralWidget(self._stack)

        self._status = QStatusBar()
        self._status_left = QLabel()
        self._status_right = QLabel()
        self._status.addWidget(self._status_left, 1)
        self._status.addPermanentWidget(self._status_right)
        self.setStatusBar(self._status)
        self.resize(1180, 760)

    # ------------------------------------------------------------- Directory
    def set_directory(self, directory: Path) -> None:
        # Only do lexical normalization (expand ~, strip .., make absolute); never use
        # resolve(): it follows symlinks to the real path, so clicking a symlink
        # directory would jump the tree from the row you clicked to somewhere else --
        # looking like "clicking A jumps to B".
        directory = Path(os.path.abspath(os.path.expanduser(str(directory))))
        if not directory.is_dir():
            return
        self._dir = directory
        self._loader.invalidate()
        files = list_images(directory, self._sort_key, self._sort_reverse,
                            self._sort_seed)
        # At the root there is no parent to go to, so that row should not appear
        parent = directory.parent if directory.parent != directory else None
        self._model.set_paths(files, parent)
        self._sync_path_bar(directory)
        self.setWindowTitle(f"{directory} — {config.APP_NAME}")
        row = self._model.first_image_row()
        if row >= 0:
            self._view.setCurrentIndex(self._model.index(row, 0))
        self._preview.show_path(self._current_path())   # clears the preview when the directory is empty
        self._update_status()

        idx = self._fs.index(str(directory))
        if idx.isValid() and idx != self._tree.currentIndex():
            # currentChanged is connected to the selectionModel, so blocking signals on
            # self._tree would not stop it; block the right place or it recurses back
            # into set_directory from _on_tree_changed.
            sel = self._tree.selectionModel()
            sel.blockSignals(True)
            self._tree.setCurrentIndex(idx)
            self._tree.scrollTo(idx, QAbstractItemView.PositionAtCenter)
            sel.blockSignals(False)

    def refresh(self) -> None:
        current = self._current_path()
        self.set_directory(self._dir)
        if current:
            row = self._model.index_of(current)
            if row >= 0:
                self._view.setCurrentIndex(self._model.index(row, 0))

    def _on_tree_changed(self, current: QModelIndex, _prev) -> None:
        path = self._fs.filePath(current)
        if path:
            self.set_directory(Path(path))

    def _set_sort(self, key: int) -> None:
        # Clicking "Random" again means reshuffle. The seed normally stays fixed so a
        # refresh() triggered by deleting an image does not reorder the whole grid.
        if key == config.SORT_RANDOM:
            self._sort_seed = (self._sort_seed + 1) & 0xFFFFFFFF
        self._sort_key = key
        self._sync_sort_indicator()
        self.refresh()

    def _toggle_sort_order(self) -> None:
        self._sort_reverse = self._sort_rev_act.isChecked()
        self._sync_sort_indicator()
        self.refresh()

    def _toggle_tree(self) -> None:
        """Collapse only the directory tree; the preview pane stays in place."""
        sizes = self._left_splitter.sizes()
        if sizes[0] > 0:
            self._tree_width = sizes[0]
            self._left_splitter.setSizes([0, sum(sizes)])
        else:
            w = getattr(self, "_tree_width", 240)
            self._left_splitter.setSizes([w, max(160, sum(sizes) - w)])

    def _toggle_preview(self, checked: bool | None = None) -> None:
        """When triggered from the menu, Qt already toggled checked before calling us;
        programmatic calls (no arg) toggle it themselves, so don't let the name fool you."""
        visible = (not self._preview.isVisible()) if checked is None else bool(checked)
        self._preview_act.setChecked(visible)
        self._preview.setVisible(visible)

    def _go_parent(self) -> None:
        up = self._model.parent_dir()
        if up is not None:
            self.set_directory(up)

    def _on_selection_changed(self, *_) -> None:
        self._preview.show_path(self._current_path())

    def _sync_icon_provider(self) -> None:
        """The directory tree's icons come from QFileSystemModel's provider; replacing it
        turns the whole tree yellow.

        Keep our own reference -- setIconProvider does not take ownership, and if it gets
        GC'd the tree goes blank.
        """
        from PySide6.QtWidgets import QFileIconProvider
        from . import theme
        on = self._win95_act.isChecked()
        self._icon_provider = theme.Win95IconProvider() if on else QFileIconProvider()
        self._fs.setIconProvider(self._icon_provider)

    def _toggle_win95(self, checked: bool | None = None) -> None:
        """Toggle the Win95 look. The style is app-level, so it is applied to QApplication directly."""
        from PySide6.QtWidgets import QApplication
        from . import theme
        on = (not self._win95_act.isChecked()) if checked is None else bool(checked)
        self._win95_act.setChecked(on)
        app = QApplication.instance()
        if app is not None:
            theme.apply(app, on)
        self._sync_icon_provider()

    # ------------------------------------------------------------- Language
    def _set_language(self, code: str) -> None:
        """Switch the UI language: set the state -> persist -> immediately refresh all UI text."""
        if i18n.current() == code:
            return
        i18n.set_language(code)
        self._settings.setValue("language", code)
        self._retranslate()

    def _retranslate(self) -> None:
        """Immediately refresh after switching language: menu, status bar, title, preview hint."""
        self._rebuild_menu()
        self._update_status()
        self.setWindowTitle(f"{self._dir} — {config.APP_NAME}")
        self._preview.update()              # the hint text in the preview pane is drawn
        if self._viewer:
            self._viewer._update_title()    # when the viewer page is open, the title follows

    def _rebuild_menu(self) -> None:
        """Rebuild the menu bar after a language change.

        First remove the old window-level actions with removeAction, then clear the menu
        bar -- a bare menuBar().clear() would leave the shortcuts and actions registered
        on the window duplicated.
        """
        old_win95 = self._win95_act.isChecked()
        old_preview = self._preview_act.isChecked()
        mb = self.menuBar()
        for a in self._menu_actions:
            self.removeAction(a)
        self._menu_actions.clear()
        mb.clear()
        self._build_menu()
        self._win95_act.setChecked(old_win95)
        self._preview_act.setChecked(old_preview)
        self._resync_menu_state()

    def _resync_menu_state(self) -> None:
        """After rebuilding the menu, put the current state (view mode / sort key / reverse) back onto the new actions."""
        for act, m in self._view_acts:
            act.setChecked(m == self._view_mode)
        self._sort_rev_act.setChecked(self._sort_reverse)
        for act, k in self._sort_acts:
            act.setChecked(k == self._sort_key)

    def _clear_cache(self) -> None:
        self._loader.clear_disk_cache()
        self.refresh()
        self._status.showMessage(tr("msg.cache_cleared"), 2500)

    def eventFilter(self, obj, ev) -> bool:
        """Enter views the image, Backspace goes to the parent. Both views have this filter installed."""
        if obj in (self._icon_view, self._list_view) and ev.type() == QEvent.KeyPress:
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._open_current()
                return True
            if ev.key() == Qt.Key_Backspace:
                self._go_parent()
                return True
        return super().eventFilter(obj, ev)

    # ------------------------------------------------------------- Selection
    def _current_path(self) -> Path | None:
        return self._model.path_at(self._view.currentIndex())

    def _selected_paths(self) -> list[Path]:
        # In list mode each row has 5 indexes (one per column); dedupe by row number, otherwise the same file would be counted 5 times
        rows = sorted({i.row() for i in self._view.selectedIndexes()})
        paths = [self._model.path_at(self._model.index(r, COL_NAME)) for r in rows]
        paths = [p for p in paths if p is not None]
        if not paths:
            cur = self._current_path()
            if cur:
                paths = [cur]
        return paths

    # ------------------------------------------------------------- Status bar
    def _update_status(self, *_) -> None:
        total = self._model.image_count()      # does not include the ".." row
        # Count by rows, not by indexes (in list mode each row has 5 indexes),
        # and exclude the ".." row -- it is not an image
        sel = len({i.row() for i in self._view.selectionModel().selectedIndexes()
                   if self._model.path_at(i) is not None})
        left = tr("status.images", total)
        if sel > 1:
            left += tr("status.selected", sel)
        self._status_left.setText(left)

        path = self._current_path()
        if path is None:
            self._status_right.setText("")
            return
        bits = [path.name]
        dims = image_dimensions(path)
        if dims:
            bits.append(human_dims(*dims))
        try:
            st = path.stat()
            bits += [format_size(st.st_size), format_mtime(st.st_mtime)]
        except OSError:
            pass
        self._status_right.setText("   ".join(bits))

    # ------------------------------------------------------------- State persistence
    def _restore_state(self) -> None:
        s = self._settings
        geo = s.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        sizes = s.value("splitter")
        if sizes:
            self._splitter.setSizes([int(x) for x in sizes])
        left_sizes = s.value("left_splitter")
        if left_sizes:
            self._left_splitter.setSizes([int(x) for x in left_sizes])
        # Note: in PySide6, value(key, type=bool) returns False (not None) when the key
        # is missing, so you cannot test `is not None`; you must check whether the key exists.
        if s.contains("preview_visible"):
            visible = bool(s.value("preview_visible"))
            self._preview_act.setChecked(visible)
            self._preview.setVisible(visible)
        edge = s.value("thumb_size", type=int)
        if edge in config.THUMB_SIZES:
            self._thumb_edge = edge
        mode = s.value("view_mode", type=int)
        if mode in config.VIEW_NAMES:
            self._view_mode = mode
            for act, m in self._view_acts:
                act.setChecked(m == mode)
        self._apply_view_mode()      # applies size and view mode in one go
        key = s.value("sort_key", type=int)
        if key in config.SORT_NAMES:
            self._sort_key = key
        self._win95_act.setChecked(
            s.value("win95_look", config.DEFAULT_WIN95_LOOK, type=bool))
        self._sort_reverse = bool(s.value("sort_reverse", False, type=bool))
        self._sort_rev_act.setChecked(self._sort_reverse)
        for act, k in self._sort_acts:
            act.setChecked(k == self._sort_key)
        self._sync_sort_indicator()   # the sort key is settled last; the arrow must be re-synced after this

    def closeEvent(self, ev) -> None:
        s = self._settings
        s.setValue("geometry", self.saveGeometry())
        s.setValue("splitter", self._splitter.sizes())
        s.setValue("left_splitter", self._left_splitter.sizes())
        s.setValue("preview_visible", self._preview_act.isChecked())
        s.setValue("win95_look", self._win95_act.isChecked())
        s.setValue("thumb_size", self._thumb_edge)   # the model is 40 in list mode; don't save that
        s.setValue("view_mode", self._view_mode)
        s.setValue("sort_key", self._sort_key)
        s.setValue("sort_reverse", self._sort_reverse)
        s.setValue("last_dir", str(self._dir))
        if self._viewer:
            self._viewer.teardown()
        self._preview.shutdown()
        self._loader.shutdown()
        super().closeEvent(ev)
