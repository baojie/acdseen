"""ACDSee Image Browser 的复刻：左边目录树，右边缩略图。

刻意保留的原版特征：
  * 只看一个目录，不递归、不建数据库、不扫全盘
  * 文件操作（删/改名/复制/移动）直接内建，不用切回文件管理器
  * 全键盘可达

这个文件只留窗口骨架：目录树、分割布局、目录切换、选择、状态栏、设置持久化。
其余按功能分了出去：
  thumbmodel.py  多列模型（两个视图共用）+ 缩略图格子的绘制
  viewpanes.py   缩略图网格 / 详细列表两个视图，切换与表头排序
  menus.py       菜单栏、右键菜单、帮助与关于
  fileops.py     文件操作（重命名 / 删除 / 复制 / 剪切 / 粘贴 / 复制到 / 移动到）
  viewhost.py    浏览 ↔ 看图 的页面切换
  helptext.py    F1 的快捷键表
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QDir, QEvent, QModelIndex, QSettings, Qt
from PySide6.QtWidgets import (QAbstractItemView, QFileSystemModel, QLabel,
                               QMainWindow, QSplitter, QStackedWidget,
                               QStatusBar, QTreeView)

from . import config
from .fileops import FileOpsMixin
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
        self._sort_seed = 0          # 只对「随机」排序有意义，见 util.list_images
        self._clipboard: tuple[str, list[Path]] | None = None   # ("copy"|"cut", paths)
        self._viewer: Viewer | None = None
        self._view_mode = config.VIEW_THUMBS
        self._thumb_edge = config.DEFAULT_THUMB_SIZE   # 图标模式用的边长，列表模式不覆盖它

        self._loader = ThumbnailLoader(self)
        self._build_ui()
        self._build_menu()
        self._restore_state()
        # 图标提供器必须无条件设一次：外观开关有默认值，光靠"设置里存过才应用"
        # 的话，首次启动会是主题开着、但目录树图标没换的半吊子状态。
        # 这里只碰自己的 QFileSystemModel，不去动全局样式 —— 那是入口和
        # 用户手动切换该干的事，构造窗口时顺手改 app 级样式副作用太大。
        self._sync_icon_provider()
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

        self._build_views()

        # 左列：目录树 + 预览窗格（原版 preview pane 就在左下方）
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
        # 到根了就没有上级可去，那一行也不该出现
        parent = directory.parent if directory.parent != directory else None
        self._model.set_paths(files, parent)
        self._sync_path_bar(directory)
        self.setWindowTitle(f"{directory} — {config.APP_NAME}")
        row = self._model.first_image_row()
        if row >= 0:
            self._view.setCurrentIndex(self._model.index(row, 0))
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

    def _go_parent(self) -> None:
        up = self._model.parent_dir()
        if up is not None:
            self.set_directory(up)

    def _on_selection_changed(self, *_) -> None:
        self._preview.show_path(self._current_path())

    def _sync_icon_provider(self) -> None:
        """目录树的图标来自 QFileSystemModel 的 provider，换掉它整棵树就变黄。

        自己留一份引用 —— setIconProvider 不接管所有权，被 GC 掉就是一片空白。
        """
        from PySide6.QtWidgets import QFileIconProvider
        from . import theme
        on = self._win95_act.isChecked()
        self._icon_provider = theme.Win95IconProvider() if on else QFileIconProvider()
        self._fs.setIconProvider(self._icon_provider)

    def _toggle_win95(self, checked: bool | None = None) -> None:
        """切 Win95 外观。样式是 app 级的，所以直接作用在 QApplication 上。"""
        from PySide6.QtWidgets import QApplication
        from . import theme
        on = (not self._win95_act.isChecked()) if checked is None else bool(checked)
        self._win95_act.setChecked(on)
        app = QApplication.instance()
        if app is not None:
            theme.apply(app, on)
        self._sync_icon_provider()

    def _clear_cache(self) -> None:
        self._loader.clear_disk_cache()
        self.refresh()
        self._status.showMessage("缩略图缓存已清空", 2500)

    def eventFilter(self, obj, ev) -> bool:
        """Enter 看图、Backspace 回上级。两个视图都装了这个过滤器。"""
        if obj in (self._icon_view, self._list_view) and ev.type() == QEvent.KeyPress:
            if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._open_current()
                return True
            if ev.key() == Qt.Key_Backspace:
                self._go_parent()
                return True
        return super().eventFilter(obj, ev)

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
        total = self._model.image_count()      # 不含 ".." 那一行
        # 按行数，不是 index 数（列表模式下一行有 5 个 index），
        # 并且要排掉 ".." 那一行 —— 它不是图片
        sel = len({i.row() for i in self._view.selectionModel().selectedIndexes()
                   if self._model.path_at(i) is not None})
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
        self._win95_act.setChecked(
            s.value("win95_look", config.DEFAULT_WIN95_LOOK, type=bool))
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
        s.setValue("win95_look", self._win95_act.isChecked())
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
