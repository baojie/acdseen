"""ACDSee Image Browser 的复刻：左边目录树，右边缩略图。

刻意保留的原版特征：
  * 只看一个目录，不递归、不建数据库、不扫全盘
  * 文件操作（删/改名/复制/移动）直接内建，不用切回文件管理器
  * 全键盘可达

这个文件只留窗口主体：UI 组装、菜单、目录切换、状态栏、设置持久化。
其余按功能分了出去：
  thumbmodel.py  缩略图列表的模型与绘制
  fileops.py     文件操作（重命名 / 删除 / 复制 / 剪切 / 粘贴 / 复制到 / 移动到）
  viewhost.py    浏览 ↔ 看图 的页面切换
  helptext.py    F1 的快捷键表
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import (QDir, QEvent, QModelIndex, QSettings, QSize, Qt)
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QFileSystemModel, QHeaderView,
                               QLabel, QListView, QMainWindow, QMenu, QMessageBox,
                               QSplitter, QStackedWidget, QStatusBar, QTreeView)

from . import config
from .fileops import FileOpsMixin
from .helptext import HELP_TEXT
from .loader import ThumbnailLoader, image_dimensions
from .preview import PreviewPane
from .thumbmodel import COL_NAME, COLUMNS, ThumbDelegate, ThumbModel
from .util import format_mtime, format_size, human_dims, list_images
from .viewer import Viewer
from .viewhost import ViewHostMixin


class Browser(ViewHostMixin, FileOpsMixin, QMainWindow):
    def __init__(self, start_dir: Path):
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self._settings = QSettings(config.ORG_NAME, config.APP_NAME)
        self._dir = start_dir
        self._sort_key = config.SORT_NAME
        self._sort_reverse = False
        self._sort_seed = 0          # 只对「随机」排序有意义，见 util.list_images
        self._clipboard: tuple[str, list[Path]] | None = None   # ("copy"|"cut", paths)
        self._viewer: Viewer | None = None
        self._view_mode = config.VIEW_THUMBS
        self._thumb_edge = config.DEFAULT_THUMB_SIZE   # 图标模式用的边长，列表模式不覆盖它

        self._loader = ThumbnailLoader(self)
        self._build_ui()
        self._build_menu()
        self._restore_state()
        self.set_directory(start_dir)

    # ------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        self._splitter = QSplitter(Qt.Horizontal, self)

        # 左：目录树
        self._fs = QFileSystemModel(self)
        self._fs.setRootPath("")
        self._fs.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Drives)
        self._tree = QTreeView()
        self._tree.setModel(self._fs)
        for col in range(1, self._fs.columnCount()):
            self._tree.hideColumn(col)
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(False)          # 动画只会拖慢感知速度
        self._tree.setExpandsOnDoubleClick(True)
        self._tree.selectionModel().currentChanged.connect(self._on_tree_changed)

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

        # 左列：目录树 + 预览窗格（原版 preview pane 就在左下方）
        self._preview = PreviewPane()
        self._left_splitter = QSplitter(Qt.Vertical)
        self._left_splitter.addWidget(self._tree)
        self._left_splitter.addWidget(self._preview)
        self._left_splitter.setStretchFactor(0, 1)
        self._left_splitter.setStretchFactor(1, 0)
        self._left_splitter.setSizes([400, 220])

        self._splitter.addWidget(self._left_splitter)
        self._splitter.addWidget(self._view_stack)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([260, 900])

        # 浏览 / 看图 是同一个窗口的两页，不是两个窗口。
        # 看图时窗口里只剩那张图 —— 这正是原版 Viewer 的样子，只是不再另开窗。
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

    # ------------------------------------------------------------- 菜单
    def _build_menu(self) -> None:
        self._browse_actions: list[QAction] = []
        mb = self.menuBar()

        m_file = mb.addMenu("文件(&F)")
        self._act("打开", "Return", self._open_current, m_file)
        self._act("在文件管理器中显示", "Ctrl+Shift+O", self._reveal, m_file)
        m_file.addSeparator()
        self._act("重命名", "F2", self._rename, m_file)
        self._act("删除", "Del", self._delete, m_file)
        m_file.addSeparator()
        self._act("复制", QKeySequence.Copy, self._copy, m_file)
        self._act("剪切", QKeySequence.Cut, self._cut, m_file)
        self._act("粘贴到当前目录", QKeySequence.Paste, self._paste, m_file)
        self._act("复制到…", "Ctrl+Shift+C", lambda: self._transfer("copy"), m_file)
        self._act("移动到…", "Ctrl+Shift+M", lambda: self._transfer("move"), m_file)
        m_file.addSeparator()
        self._act("退出", "Ctrl+Q", self.close, m_file, browse_only=False)

        m_view = mb.addMenu("查看(&V)")
        self._view_acts: list[tuple[QAction, int]] = []
        vgrp = QActionGroup(self); vgrp.setExclusive(True)
        for mode, name in config.VIEW_NAMES.items():
            a = QAction(name, self, checkable=True)
            a.setShortcut(QKeySequence(f"Ctrl+{mode + 1}"))
            a.setChecked(mode == self._view_mode)
            a.triggered.connect(lambda _=False, m=mode: self._set_view_mode(m))
            vgrp.addAction(a); m_view.addAction(a); self.addAction(a)
            self._view_acts.append((a, mode))
            self._browse_actions.append(a)
        self._act("切换缩略图 / 列表", "F8", self._toggle_view_mode, m_view)
        m_view.addSeparator()
        self._act("全选", QKeySequence.SelectAll, lambda: self._view.selectAll(), m_view)
        self._act("刷新", "F5", self.refresh, m_view)
        m_view.addSeparator()
        self._act("放大缩略图", "Ctrl++", lambda: self._step_thumb(+1), m_view)
        self._act("缩小缩略图", "Ctrl+-", lambda: self._step_thumb(-1), m_view)
        m_view.addSeparator()
        self._act("切换目录树", "F9", self._toggle_tree, m_view)
        self._preview_act = QAction("预览窗格", self, checkable=True)
        self._preview_act.setChecked(True)
        self._preview_act.triggered.connect(self._toggle_preview)
        m_view.addAction(self._preview_act)
        self._act("清空缩略图缓存", None, self._clear_cache, m_view)

        m_sort = mb.addMenu("排序(&S)")
        grp = QActionGroup(self); grp.setExclusive(True)
        self._sort_acts: list[tuple[QAction, int]] = []
        for key, name in config.SORT_NAMES.items():
            if key == config.SORT_PIXELS:
                m_sort.addSeparator()        # 以下几项要读文件头，和上面的分开
            a = QAction(f"按{name}", self, checkable=True)
            a.setChecked(key == self._sort_key)
            if key in config.SORT_NEEDS_DIMS:
                a.setToolTip("需要读取每个文件的图片头，大目录首次会慢一下")
            a.triggered.connect(lambda _=False, k=key: self._set_sort(k))
            grp.addAction(a); m_sort.addAction(a)
            self._sort_acts.append((a, key))
        m_sort.addSeparator()
        self._sort_rev_act = QAction("倒序", self, checkable=True)
        self._sort_rev_act.triggered.connect(self._toggle_sort_order)
        m_sort.addAction(self._sort_rev_act)

        m_show = mb.addMenu("看图(&I)")
        self._act("查看选中图片", "Return", self._open_current, m_show)
        # 包一层 lambda：triggered 会塞个 checked 布尔进来，直接连会被当成起始张号
        self._act("从第一张开始幻灯片", "Ctrl+S", lambda: self._start_slideshow(0), m_show)

        m_help = mb.addMenu("帮助(&H)")
        self._act("快捷键", "F1", self._show_help, m_help, browse_only=False)
        self._act("关于", None, self._show_about, m_help, browse_only=False)

    def _act(self, text, shortcut, slot, menu, browse_only: bool = True) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut if isinstance(shortcut, QKeySequence) else QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        self.addAction(a)   # 让快捷键在整窗口生效
        if browse_only:
            # 这些快捷键（Del / Enter / F5 / Ctrl+C…）和看图器的按键撞车，
            # 且 WindowShortcut 上下文会抢在 Viewer.keyPressEvent 之前触发。
            # 进入看图模式时统一禁用。
            self._browse_actions.append(a)
        return a

    # ------------------------------------------------------------- 目录
    def set_directory(self, directory: Path) -> None:
        # 只做词法规范化（展开 ~、去掉 ..、转绝对路径），绝不能用 resolve()：
        # 它会跟着软链接走到真实路径，于是点软链接目录时树上会从你点的那一行
        # 蹦到别处去 —— 看起来就是"点 A 跳到 B"。
        directory = Path(os.path.abspath(os.path.expanduser(str(directory))))
        if not directory.is_dir():
            return
        self._dir = directory
        self._loader.invalidate()
        files = list_images(directory, self._sort_key, self._sort_reverse,
                            self._sort_seed)
        self._model.set_paths(files)
        self.setWindowTitle(f"{directory} — {config.APP_NAME}")
        if files:
            self._view.setCurrentIndex(self._model.index(0, 0))
        self._preview.show_path(self._current_path())   # 空目录时清空预览
        self._update_status()

        idx = self._fs.index(str(directory))
        if idx.isValid() and idx != self._tree.currentIndex():
            # currentChanged 连在 selectionModel 上，拦 self._tree 的信号是拦不住的，
            # 不拦对地方就会从 _on_tree_changed 里递归回 set_directory。
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
        # 再点一次「随机」= 重新洗牌。平时 seed 不动，删张图触发的 refresh()
        # 才不会把整个网格重排一遍。
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
        """只收目录树，预览窗格留在原地。"""
        sizes = self._left_splitter.sizes()
        if sizes[0] > 0:
            self._tree_width = sizes[0]
            self._left_splitter.setSizes([0, sum(sizes)])
        else:
            w = getattr(self, "_tree_width", 240)
            self._left_splitter.setSizes([w, max(160, sum(sizes) - w)])

    def _toggle_preview(self, checked: bool | None = None) -> None:
        """菜单触发时 Qt 已经把 checked 翻好了传进来；
        程序化调用（无参）则自己翻转，别让这个名字骗人。"""
        visible = (not self._preview.isVisible()) if checked is None else bool(checked)
        self._preview_act.setChecked(visible)
        self._preview.setVisible(visible)

    def _on_selection_changed(self, *_) -> None:
        self._preview.show_path(self._current_path())

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

    def _clear_cache(self) -> None:
        self._loader.clear_disk_cache()
        self.refresh()
        self._status.showMessage("缩略图缓存已清空", 2500)

    # ------------------------------------------------------------- 选择
    def _current_path(self) -> Path | None:
        return self._model.path_at(self._view.currentIndex())

    def _selected_paths(self) -> list[Path]:
        # 列表模式下一行有 5 个 index（每列一个），按行号去重，否则同一个文件会被数 5 遍
        rows = sorted({i.row() for i in self._view.selectedIndexes()})
        paths = [self._model.path_at(self._model.index(r, COL_NAME)) for r in rows]
        paths = [p for p in paths if p is not None]
        if not paths:
            cur = self._current_path()
            if cur:
                paths = [cur]
        return paths

    # ------------------------------------------------------------- 状态栏
    def _update_status(self, *_) -> None:
        total = self._model.rowCount()
        # 按行数，不是 index 数 —— 列表模式下一行有 5 个 index
        sel = len({i.row() for i in self._view.selectionModel().selectedIndexes()})
        left = f"{total} 张图片"
        if sel > 1:
            left += f"，已选 {sel}"
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

    # ------------------------------------------------------------- 杂项
    def _file_context_menu(self, pos) -> None:
        m = self._build_file_menu(pos)
        m.exec(self._view.viewport().mapToGlobal(pos))

    def _build_file_menu(self, pos) -> QMenu:
        """构造缩略图右键菜单。和 exec 分开，测试才能不弹模态窗就检查内容。"""
        # 作用于右键点中的那一项。Qt 右键也会移动当前项，两者通常一致，
        # 但点在空白处时 indexAt 无效，那就退回当前项。
        idx = self._view.indexAt(pos)
        if not idx.isValid():
            idx = self._view.currentIndex()

        m = QMenu(self)
        m.addAction("查看\tEnter", self._open_current)
        row = idx.row()
        act = m.addAction("幻灯演示", lambda: self._start_slideshow(row))
        act.setEnabled(idx.isValid())
        m.addSeparator()
        m.addAction("重命名\tF2", self._rename)
        m.addAction("删除\tDel", self._delete)
        m.addSeparator()
        m.addAction("复制\tCtrl+C", self._copy)
        m.addAction("剪切\tCtrl+X", self._cut)
        m.addAction("复制到…", lambda: self._transfer("copy"))
        m.addAction("移动到…", lambda: self._transfer("move"))
        return m

    def eventFilter(self, obj, ev) -> bool:
        if obj is self._view and ev.type() == QEvent.KeyPress:
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._open_current()
                return True
            if ev.key() == Qt.Key_Backspace:
                self.set_directory(self._dir.parent)
                return True
        return super().eventFilter(obj, ev)

    def _show_help(self) -> None:
        QMessageBox.information(self, "快捷键", HELP_TEXT)

    def _show_about(self) -> None:
        QMessageBox.about(
            self, f"关于 {config.APP_NAME}",
            f"<b>{config.APP_NAME}</b><br><br>"
            "1996 年 ACDSee 1.2x 的复刻：一个浏览器 + 一个看图器，<br>"
            "没有数据库，没有编辑器，没有云。<br><br>"
            "只求打开得快、翻页不卡、手不离键盘。")

    # ------------------------------------------------------------- 状态保存
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
        # 注意：PySide6 里 value(key, type=bool) 在键缺失时返回 False 而非 None，
        # 不能用 `is not None` 判断，必须查键是否存在。
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
        self._apply_view_mode()      # 一次把尺寸和视图模式都落到位
        key = s.value("sort_key", type=int)
        if key in config.SORT_NAMES:
            self._sort_key = key
        self._sort_reverse = bool(s.value("sort_reverse", False, type=bool))
        self._sort_rev_act.setChecked(self._sort_reverse)
        for act, k in self._sort_acts:
            act.setChecked(k == self._sort_key)
        self._sync_sort_indicator()   # 排序是最后才定下来的，箭头要在这之后再对一次

    def closeEvent(self, ev) -> None:
        s = self._settings
        s.setValue("geometry", self.saveGeometry())
        s.setValue("splitter", self._splitter.sizes())
        s.setValue("left_splitter", self._left_splitter.sizes())
        s.setValue("preview_visible", self._preview_act.isChecked())
        s.setValue("thumb_size", self._thumb_edge)   # 列表模式下模型是 40，别存那个
        s.setValue("view_mode", self._view_mode)
        s.setValue("sort_key", self._sort_key)
        s.setValue("sort_reverse", self._sort_reverse)
        s.setValue("last_dir", str(self._dir))
        if self._viewer:
            self._viewer.teardown()
        self._preview.shutdown()
        self._loader.shutdown()
        super().closeEvent(ev)
