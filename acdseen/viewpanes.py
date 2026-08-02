"""浏览器右侧的两个视图，以及它们之间的切换。

缩略图网格是 QListView（只显示第 0 列，自己画格子），详细列表是 QTreeView
（多列 + 原生表头）。两者共用同一个模型和同一个选择模型，所以切视图时当前项
和选中集自动同步，不用手动搬。

其余代码只认 self._view —— 那是个属性，返回当前生效的那一个。

依赖宿主提供：_loader _model _view_mode _thumb_edge _sort_key _sort_reverse
             _sort_rev_act _view_acts _open_index() _update_status()
             _on_selection_changed() _file_context_menu() _current_path()
             _set_sort() eventFilter()
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QListView,
                               QStackedWidget, QTreeView)

from . import config
from .thumbmodel import COL_NAME, COLUMNS, ThumbDelegate, ThumbModel


class ViewPanesMixin:
    def _build_views(self) -> None:
        # 右：缩略图网格 / 详细列表，两个视图共用一个模型和一个选择模型
        self._model = ThumbModel(self._loader, self)

        self._icon_view = QListView()
        self._icon_view.setModel(self._model)
        self._icon_view.setViewMode(QListView.IconMode)
        self._icon_view.setResizeMode(QListView.Adjust)
        self._icon_view.setMovement(QListView.Static)
        self._icon_view.setUniformItemSizes(True)   # 关键：避免 Qt 遍历全部项算尺寸
        self._icon_view.setWordWrap(True)
        self._icon_view.setSpacing(6)
        self._icon_view.setItemDelegate(ThumbDelegate(self._icon_view, self))

        self._list_view = QTreeView()
        self._list_view.setModel(self._model)
        self._list_view.setRootIsDecorated(False)
        self._list_view.setUniformRowHeights(True)
        self._list_view.setAllColumnsShowFocus(True)
        self._list_view.setAlternatingRowColors(True)
        self._list_view.setIconSize(QSize(config.LIST_THUMB_SIZE, config.LIST_THUMB_SIZE))
        # 共享选择模型：两个视图的当前项和选中集自动同步，切视图不用手动搬
        self._list_view.setSelectionModel(self._icon_view.selectionModel())

        hdr = self._list_view.header()
        hdr.setSectionsClickable(True)
        hdr.setSortIndicatorShown(True)
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)   # 名称吃掉剩余宽度
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
        # 光连 currentChanged 不够：框选一片时当前项不变，"已选 N" 就永远不刷新
        sel.selectionChanged.connect(self._update_status)

        self._view_stack = QStackedWidget()
        self._view_stack.addWidget(self._icon_view)
        self._view_stack.addWidget(self._list_view)
        self._apply_view_mode()

    @property
    def _view(self) -> QAbstractItemView:
        """当前生效的那个视图。其余代码只认这个，不关心是网格还是列表。"""
        return self._list_view if self._view_mode == config.VIEW_LIST else self._icon_view

    def _apply_grid(self) -> None:
        edge = self._model.thumb_size()
        fm = self._icon_view.fontMetrics()
        text_h = fm.height() * config.THUMB_LABEL_LINES + 6
        self._icon_view.setIconSize(QSize(edge, edge))
        self._icon_view.setGridSize(QSize(edge + 22, edge + text_h + 12))

    def _apply_view_mode(self) -> None:
        """在缩略图网格和详细列表之间切。模型不换，只换视图。"""
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
        if keep:                                 # set_thumb_size 会重置模型，选中项要找回来
            row = self._model.index_of(keep)
            if row >= 0:
                idx = self._model.index(row, 0)
                self._view.setCurrentIndex(idx)
                self._view.scrollTo(idx, QAbstractItemView.EnsureVisible)
        self._view.setFocus(Qt.OtherFocusReason)

    # ------------------------------------------------------------- 表头排序
    def _on_header_clicked(self, section: int) -> None:
        """点表头排序：点当前列翻转正倒序，点别的列换排序键并回到正序。"""
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
        """让表头的箭头跟上当前排序 —— 从菜单改的排序也要反映出来。
        随机排序不对应任何一列，那就把箭头收掉。"""
        hdr = self._list_view.header()
        section = next((i for i, (_t, k, _w) in enumerate(COLUMNS) if k == self._sort_key), -1)
        hdr.blockSignals(True)                   # setSortIndicator 不该再触发一次排序
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
            # 列表模式的行高是固定的，改缩略图尺寸没有意义 —— 顺手切回去
            self._set_view_mode(config.VIEW_THUMBS)
            return
        sizes = config.THUMB_SIZES
        i = min(range(len(sizes)), key=lambda j: abs(sizes[j] - self._thumb_edge))
        i = max(0, min(len(sizes) - 1, i + direction))
        self._thumb_edge = sizes[i]
        self._model.set_thumb_size(self._thumb_edge)
        self._apply_grid()
