"""The two views on the browser's right side, and switching between them.

The thumbnail grid is a QListView (only column 0 is shown, cells painted by our own
delegate), and the detail list is a QTreeView (multi-column + native header). Both share
the same model and the same selection model, so the current item and the selected set
stay in sync automatically when switching views, without manual copying.

All other code only knows self._view -- a property that returns whichever is active.

Depends on the host providing: _loader _model _view_mode _thumb_edge _sort_key _sort_reverse
                               _sort_rev_act _view_acts _open_index() _update_status()
                               _on_selection_changed() _file_context_menu() _current_path()
                               _set_sort() eventFilter()
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHeaderView,
                               QListView, QStackedWidget, QTreeView, QVBoxLayout,
                               QWidget)

from . import config
from .thumbmodel import COL_NAME, COLUMNS, ThumbDelegate, ThumbModel


class ViewPanesMixin:
    def _build_views(self) -> None:
        # Right: thumbnail grid / detail list, both views share one model and one selection model
        self._model = ThumbModel(self._loader, self)

        self._icon_view = QListView()
        self._icon_view.setModel(self._model)
        self._icon_view.setViewMode(QListView.IconMode)
        self._icon_view.setResizeMode(QListView.Adjust)
        self._icon_view.setMovement(QListView.Static)
        self._icon_view.setUniformItemSizes(True)   # key: avoid Qt iterating all items to compute sizes
        self._icon_view.setWordWrap(True)
        self._icon_view.setSpacing(6)
        self._icon_view.setItemDelegate(ThumbDelegate(self._icon_view, self))

        self._list_view = QTreeView()
        self._list_view.setModel(self._model)
        self._list_view.setRootIsDecorated(False)
        self._list_view.setUniformRowHeights(True)
        self._list_view.setAllColumnsShowFocus(True)
        self._list_view.setIconSize(QSize(config.LIST_THUMB_SIZE, config.LIST_THUMB_SIZE))
        # Shared selection model: the two views' current item and selected set sync automatically, no manual copying when switching
        self._list_view.setSelectionModel(self._icon_view.selectionModel())

        hdr = self._list_view.header()
        hdr.setSectionsClickable(True)
        hdr.setSortIndicatorShown(True)
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)   # the name column eats the remaining width
        for i, (_t, _k, w) in enumerate(COLUMNS):
            if w:
                self._list_view.setColumnWidth(i, w)
        hdr.sectionClicked.connect(self._on_header_clicked)

        for v in (self._icon_view, self._list_view):
            v.setSelectionBehavior(QAbstractItemView.SelectRows)
            v.setSelectionMode(QAbstractItemView.ExtendedSelection)
            v.setEditTriggers(QAbstractItemView.NoEditTriggers)
            v.doubleClicked.connect(self._open_index)
            v.installEventFilter(self)
            v.setContextMenuPolicy(Qt.CustomContextMenu)
            v.customContextMenuRequested.connect(self._file_context_menu)

        sel = self._icon_view.selectionModel()
        sel.currentChanged.connect(self._update_status)
        sel.currentChanged.connect(self._on_selection_changed)
        # Connecting only currentChanged is not enough: when marquee-selecting a range
        # the current item does not change, so "N selected" would never refresh
        sel.selectionChanged.connect(self._update_status)

        # Path bar: the sunken box at the top-right in the original that shows the current directory, with a dropdown arrow at the right end
        self._path_bar = QComboBox()
        self._path_bar.setEditable(True)
        self._path_bar.setInsertPolicy(QComboBox.NoInsert)
        self._path_bar.lineEdit().returnPressed.connect(self._on_path_entered)
        self._path_bar.activated.connect(self._on_path_picked)

        self._view_stack = QStackedWidget()
        self._view_stack.addWidget(self._icon_view)
        self._view_stack.addWidget(self._list_view)

        self._right_pane = QWidget()
        lay = QVBoxLayout(self._right_pane)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)
        lay.addWidget(self._path_bar)
        lay.addWidget(self._view_stack, 1)
        self._apply_view_mode()

    # ------------------------------------------------------------- Path bar
    def _sync_path_bar(self, directory) -> None:
        """Refresh the path bar to the current directory, listing each ancestor in the dropdown.

        Signals must be blocked: stuffing items into a QComboBox triggers activated,
        and without blocking it would recurse back into set_directory from set_directory.
        """
        bar = self._path_bar
        bar.blockSignals(True)
        bar.clear()
        chain, p = [], directory
        while True:
            chain.append(p)
            if p.parent == p:
                break
            p = p.parent
        bar.addItems([str(x) for x in chain])
        bar.setCurrentIndex(0)
        bar.setEditText(str(directory))
        bar.blockSignals(False)

    def _on_path_entered(self) -> None:
        from pathlib import Path
        text = self._path_bar.currentText().strip()
        if text:
            self.set_directory(Path(text))
        self._view.setFocus(Qt.OtherFocusReason)

    def _on_path_picked(self, i: int) -> None:
        from pathlib import Path
        text = self._path_bar.itemText(i)
        if text:
            self.set_directory(Path(text))
        self._view.setFocus(Qt.OtherFocusReason)

    @property
    def _view(self) -> QAbstractItemView:
        """The currently active view. All other code only knows this one, and doesn't care whether it's a grid or a list."""
        return self._list_view if self._view_mode == config.VIEW_LIST else self._icon_view

    def _apply_grid(self) -> None:
        edge = self._model.thumb_size()
        fm = self._icon_view.fontMetrics()
        text_h = fm.height() * config.THUMB_LABEL_LINES + 6
        self._icon_view.setIconSize(QSize(edge, edge))
        self._icon_view.setGridSize(QSize(edge + 22, edge + text_h + 12))

    def _apply_view_mode(self) -> None:
        """Switch between the thumbnail grid and the detail list. The model stays; only the view changes."""
        if self._view_mode == config.VIEW_LIST:
            self._model.set_thumb_size(config.LIST_THUMB_SIZE)
        else:
            self._model.set_thumb_size(self._thumb_edge)
            self._apply_grid()
        self._view_stack.setCurrentWidget(self._view)
        self._sync_sort_indicator()

    def _set_view_mode(self, mode: int) -> None:
        if mode == self._view_mode:
            return
        keep = self._current_path()
        self._view_mode = mode
        self._apply_view_mode()
        for act, m in getattr(self, "_view_acts", []):
            act.setChecked(m == mode)
        if keep:                                 # set_thumb_size resets the model; the selection must be restored
            row = self._model.index_of(keep)
            if row >= 0:
                idx = self._model.index(row, 0)
                self._view.setCurrentIndex(idx)
                self._view.scrollTo(idx, QAbstractItemView.EnsureVisible)
        self._view.setFocus(Qt.OtherFocusReason)

    # ------------------------------------------------------------- Header sorting
    def _on_header_clicked(self, section: int) -> None:
        """Click a header to sort: clicking the current column flips ascending/descending, clicking another column switches the sort key and returns to ascending."""
        if not 0 <= section < len(COLUMNS):
            return
        key = COLUMNS[section][1]
        if key == self._sort_key:
            self._sort_reverse = not self._sort_reverse
            self._sort_rev_act.setChecked(self._sort_reverse)
        else:
            self._sort_reverse = False
            self._sort_rev_act.setChecked(False)
        self._set_sort(key)

    def _sync_sort_indicator(self) -> None:
        """Keep the header arrow in sync with the current sort -- sorting changed from
        the menu must show up too. Random sort maps to no column, so hide the arrow."""
        hdr = self._list_view.header()
        section = next((i for i, (_t, k, _w) in enumerate(COLUMNS) if k == self._sort_key), -1)
        hdr.blockSignals(True)                   # setSortIndicator should not trigger another sort
        if section < 0:
            hdr.setSortIndicatorShown(False)
        else:
            hdr.setSortIndicatorShown(True)
            hdr.setSortIndicator(section,
                                 Qt.DescendingOrder if self._sort_reverse else Qt.AscendingOrder)
        hdr.blockSignals(False)

    def _toggle_view_mode(self) -> None:
        self._set_view_mode(config.VIEW_THUMBS if self._view_mode == config.VIEW_LIST
                            else config.VIEW_LIST)

    def _step_thumb(self, direction: int) -> None:
        if self._view_mode == config.VIEW_LIST:
            # List-mode row height is fixed, so changing thumbnail size is pointless -- switch back while we're at it
            self._set_view_mode(config.VIEW_THUMBS)
            return
        sizes = config.THUMB_SIZES
        i = min(range(len(sizes)), key=lambda j: abs(sizes[j] - self._thumb_edge))
        i = max(0, min(len(sizes) - 1, i + direction))
        self._thumb_edge = sizes[i]
        self._model.set_thumb_size(self._thumb_edge)
        self._apply_grid()
