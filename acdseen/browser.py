"""ACDSee Image Browser 的复刻：左边目录树，右边缩略图。

刻意保留的原版特征：
  * 只看一个目录，不递归、不建数据库、不扫全盘
  * 文件操作（删/改名/复制/移动）直接内建，不用切回文件管理器
  * 全键盘可达
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import (QAbstractListModel, QDir, QEvent, QModelIndex,
                            QRect, QSettings, QSize, Qt, QTimer, Signal)
from PySide6.QtGui import (QAction, QActionGroup, QColor, QIcon, QImage,
                           QKeySequence, QPainter, QPixmap)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFileSystemModel,
                               QInputDialog, QLabel, QLineEdit, QListView,
                               QMainWindow, QMenu, QMessageBox, QSplitter,
                               QStackedWidget, QStatusBar, QStyle,
                               QStyledItemDelegate, QTreeView, QWidget)

from . import config
from .loader import ThumbnailLoader, image_dimensions
from .preview import PreviewPane
from .util import format_mtime, format_size, human_dims, list_images
from .viewer import Viewer


class ThumbModel(QAbstractListModel):
    """图片列表模型。缩略图按需异步加载 —— Qt 只为可见项调 data()，
    所以这里的 lazy request 天然只处理视口内的文件。"""

    def __init__(self, loader: ThumbnailLoader, parent=None):
        super().__init__(parent)
        self._paths: list[Path] = []
        self._thumbs: dict[Path, QIcon] = {}
        self._requested: set[Path] = set()
        self._edge = config.DEFAULT_THUMB_SIZE
        self._loader = loader
        self._loader.ready.connect(self._on_thumb)
        self._placeholder = self._make_placeholder(self._edge)

    # -- 数据 --
    def set_paths(self, paths: list[Path]) -> None:
        self.beginResetModel()
        self._paths = paths
        self._thumbs.clear()
        self._requested.clear()
        self.endResetModel()

    def paths(self) -> list[Path]:
        return self._paths

    def path_at(self, index: QModelIndex) -> Path | None:
        if index.isValid() and 0 <= index.row() < len(self._paths):
            return self._paths[index.row()]
        return None

    def index_of(self, path: Path) -> int:
        try:
            return self._paths.index(path)
        except ValueError:
            return -1

    def remove_paths(self, paths: set[Path]) -> None:
        keep = [p for p in self._paths if p not in paths]
        if len(keep) != len(self._paths):
            self.set_paths(keep)

    def set_thumb_size(self, edge: int) -> None:
        if edge == self._edge:
            return
        self._edge = edge
        self._placeholder = self._make_placeholder(edge)
        self._thumbs.clear()
        self._requested.clear()
        self._loader.invalidate()
        self.beginResetModel()
        self.endResetModel()

    def thumb_size(self) -> int:
        return self._edge

    # -- QAbstractListModel --
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._paths)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        path = self.path_at(index)
        if path is None:
            return None
        if role == Qt.DisplayRole:
            return path.name
        if role == Qt.DecorationRole:
            icon = self._thumbs.get(path)
            if icon is not None:
                return icon
            if path not in self._requested:
                self._requested.add(path)
                self._loader.request(path, self._edge)
            return self._placeholder
        if role == Qt.ToolTipRole:
            return self._tooltip(path)
        return None

    def _tooltip(self, path: Path) -> str:
        parts = [path.name]
        try:
            st = path.stat()
            parts.append(f"{format_size(st.st_size)}   {format_mtime(st.st_mtime)}")
        except OSError:
            pass
        dims = image_dimensions(path)
        if dims:
            parts.append(human_dims(*dims))
        return "\n".join(parts)

    def _on_thumb(self, path: Path, img: QImage | None) -> None:
        if path not in self._requested:
            return
        row = self.index_of(path)
        if row < 0:
            return
        if img is None:
            self._thumbs[path] = self._make_broken(self._edge)
        else:
            self._thumbs[path] = QIcon(QPixmap.fromImage(img))
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [Qt.DecorationRole])

    # -- 占位图 --
    @staticmethod
    def _make_placeholder(edge: int) -> QIcon:
        pm = QPixmap(edge, edge)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setPen(QColor(120, 120, 128, 110))
        p.setBrush(QColor(150, 150, 158, 28))
        m = edge // 6
        p.drawRect(m, m, edge - 2 * m, edge - 2 * m)
        p.end()
        return QIcon(pm)

    @staticmethod
    def _make_broken(edge: int) -> QIcon:
        pm = QPixmap(edge, edge)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setPen(QColor(190, 90, 90, 170))
        m = edge // 5
        p.drawRect(m, m, edge - 2 * m, edge - 2 * m)
        p.drawLine(m, m, edge - m, edge - m)
        p.drawLine(edge - m, m, m, edge - m)
        p.end()
        return QIcon(pm)


class ThumbDelegate(QStyledItemDelegate):
    """自己画格子：图在上半区垂直居中，文件名固定贴底，选中高亮框住整格。

    交给 Qt 默认画的话，不同宽高比的缩略图会让文件名基线参差不齐，
    选中框也只圈住文字 —— 一眼就是"没做完"的样子。
    """

    def __init__(self, view: QListView, parent=None):
        super().__init__(parent)
        self._view = view

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        painter.save()
        rect = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        pal = option.palette

        if selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(pal.highlight())
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

        fm = painter.fontMetrics()
        text_h = fm.height() * config.THUMB_LABEL_LINES
        pad = 5
        icon_area = QRect(rect.left() + pad, rect.top() + pad,
                          rect.width() - 2 * pad,
                          rect.height() - text_h - 3 * pad)

        icon = index.data(Qt.DecorationRole)
        if isinstance(icon, QIcon):
            pm = icon.pixmap(icon_area.size())
            if not pm.isNull():
                x = icon_area.left() + (icon_area.width() - pm.width()) // 2
                y = icon_area.top() + (icon_area.height() - pm.height()) // 2
                painter.drawPixmap(x, y, pm)

        text_rect = QRect(rect.left() + 3, icon_area.bottom() + pad,
                          rect.width() - 6, text_h)
        painter.setPen(pal.highlightedText().color() if selected else pal.text().color())
        name = index.data(Qt.DisplayRole) or ""
        painter.drawText(text_rect,
                         Qt.AlignHCenter | Qt.AlignTop | Qt.TextWrapAnywhere,
                         self._elide(name, fm, text_rect.width()))
        painter.restore()

    @staticmethod
    def _elide(name: str, fm, width: int) -> str:
        """两行放不下就中间省略 —— 扩展名比中间那截更值得保留。"""
        if fm.horizontalAdvance(name) <= width * config.THUMB_LABEL_LINES:
            return name
        return fm.elidedText(name, Qt.ElideMiddle, width * config.THUMB_LABEL_LINES)

    def sizeHint(self, option, index) -> QSize:
        return self._view.gridSize()


class Browser(QMainWindow):
    def __init__(self, start_dir: Path):
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self._settings = QSettings(config.ORG_NAME, config.APP_NAME)
        self._dir = start_dir
        self._sort_key = config.SORT_NAME
        self._sort_reverse = False
        self._clipboard: tuple[str, list[Path]] | None = None   # ("copy"|"cut", paths)
        self._viewer: Viewer | None = None

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

        # 右：缩略图
        self._model = ThumbModel(self._loader, self)
        self._view = QListView()
        self._view.setModel(self._model)
        self._view.setViewMode(QListView.IconMode)
        self._view.setResizeMode(QListView.Adjust)
        self._view.setMovement(QListView.Static)
        self._view.setUniformItemSizes(True)   # 关键：避免 Qt 遍历全部项算尺寸
        self._view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._view.setWordWrap(True)
        self._view.setSpacing(6)
        self._view.setItemDelegate(ThumbDelegate(self._view, self))
        self._view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._view.doubleClicked.connect(self._open_index)
        self._view.selectionModel().currentChanged.connect(self._update_status)
        self._view.selectionModel().currentChanged.connect(self._on_selection_changed)
        self._view.installEventFilter(self)
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._file_context_menu)
        self._apply_grid()

        # 左列：目录树 + 预览窗格（原版 preview pane 就在左下方）
        self._preview = PreviewPane()
        self._left_splitter = QSplitter(Qt.Vertical)
        self._left_splitter.addWidget(self._tree)
        self._left_splitter.addWidget(self._preview)
        self._left_splitter.setStretchFactor(0, 1)
        self._left_splitter.setStretchFactor(1, 0)
        self._left_splitter.setSizes([400, 220])

        self._splitter.addWidget(self._left_splitter)
        self._splitter.addWidget(self._view)
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

    def _apply_grid(self) -> None:
        edge = self._model.thumb_size()
        fm = self._view.fontMetrics()
        text_h = fm.height() * config.THUMB_LABEL_LINES + 6
        self._view.setIconSize(QSize(edge, edge))
        self._view.setGridSize(QSize(edge + 22, edge + text_h + 12))

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
        self._act("全选", QKeySequence.SelectAll, self._view.selectAll, m_view)
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
        for key, name in config.SORT_NAMES.items():
            a = QAction(f"按{name}", self, checkable=True)
            a.setChecked(key == self._sort_key)
            a.triggered.connect(lambda _=False, k=key: self._set_sort(k))
            grp.addAction(a); m_sort.addAction(a)
        m_sort.addSeparator()
        self._sort_rev_act = QAction("倒序", self, checkable=True)
        self._sort_rev_act.triggered.connect(self._toggle_sort_order)
        m_sort.addAction(self._sort_rev_act)

        m_show = mb.addMenu("看图(&I)")
        self._act("查看选中图片", "Return", self._open_current, m_show)
        self._act("从第一张开始幻灯片", "F5" if False else "Ctrl+S", self._start_slideshow, m_show)

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
        directory = directory.expanduser().resolve()
        if not directory.is_dir():
            return
        self._dir = directory
        self._loader.invalidate()
        files = list_images(directory, self._sort_key, self._sort_reverse)
        self._model.set_paths(files)
        self.setWindowTitle(f"{directory} — {config.APP_NAME}")
        if files:
            self._view.setCurrentIndex(self._model.index(0, 0))
        self._preview.show_path(self._current_path())   # 空目录时清空预览
        self._update_status()

        idx = self._fs.index(str(directory))
        if idx.isValid():
            self._tree.blockSignals(True)
            self._tree.setCurrentIndex(idx)
            self._tree.scrollTo(idx, QAbstractItemView.PositionAtCenter)
            self._tree.blockSignals(False)

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
        self._sort_key = key
        self.refresh()

    def _toggle_sort_order(self) -> None:
        self._sort_reverse = self._sort_rev_act.isChecked()
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
        sizes = config.THUMB_SIZES
        cur = self._model.thumb_size()
        i = min(range(len(sizes)), key=lambda j: abs(sizes[j] - cur))
        i = max(0, min(len(sizes) - 1, i + direction))
        self._model.set_thumb_size(sizes[i])
        self._apply_grid()

    def _clear_cache(self) -> None:
        self._loader.clear_disk_cache()
        self.refresh()
        self._status.showMessage("缩略图缓存已清空", 2500)

    # ------------------------------------------------------------- 选择
    def _current_path(self) -> Path | None:
        return self._model.path_at(self._view.currentIndex())

    def _selected_paths(self) -> list[Path]:
        paths = [self._model.path_at(i) for i in self._view.selectedIndexes()]
        paths = [p for p in paths if p is not None]
        if not paths:
            cur = self._current_path()
            if cur:
                paths = [cur]
        return paths

    # ------------------------------------------------------------- 看图
    def _open_index(self, index: QModelIndex) -> None:
        path = self._model.path_at(index)
        if path:
            self._open_viewer(self._model.index_of(path))

    def _open_current(self) -> None:
        idx = self._view.currentIndex()
        if idx.isValid():
            self._open_index(idx)

    def _start_slideshow(self) -> None:
        if self._model.rowCount() == 0:
            return
        v = self._open_viewer(0)
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

    # ------------------------------------------------------------- 文件操作
    def _rename(self) -> None:
        path = self._current_path()
        if path is None:
            return
        new, ok = QInputDialog.getText(self, "重命名", "新名称：",
                                       QLineEdit.Normal, path.name)
        if not ok or not new.strip() or new == path.name:
            return
        target = path.with_name(new.strip())
        if target.exists():
            QMessageBox.warning(self, "重命名", f"{target.name} 已存在。")
            return
        try:
            path.rename(target)
        except OSError as e:
            QMessageBox.warning(self, "重命名失败", str(e))
            return
        self.refresh()
        row = self._model.index_of(target)
        if row >= 0:
            self._view.setCurrentIndex(self._model.index(row, 0))

    def _delete(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        msg = f"删除 {paths[0].name}？" if len(paths) == 1 else f"删除选中的 {len(paths)} 个文件？"
        if QMessageBox.question(self, "删除", msg,
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return
        row = self._view.currentIndex().row()
        failed = []
        for p in paths:
            try:
                p.unlink()
            except OSError as e:
                failed.append(f"{p.name}: {e}")
        self._model.remove_paths(set(paths))
        if self._model.rowCount():
            self._view.setCurrentIndex(
                self._model.index(min(row, self._model.rowCount() - 1), 0))
        if failed:
            QMessageBox.warning(self, "部分删除失败", "\n".join(failed[:10]))
        self._update_status()

    def _copy(self) -> None:
        paths = self._selected_paths()
        if paths:
            self._clipboard = ("copy", paths)
            self._status.showMessage(f"已复制 {len(paths)} 个文件", 2000)

    def _cut(self) -> None:
        paths = self._selected_paths()
        if paths:
            self._clipboard = ("cut", paths)
            self._status.showMessage(f"已剪切 {len(paths)} 个文件", 2000)

    def _paste(self) -> None:
        if not self._clipboard:
            return
        mode, paths = self._clipboard
        self._do_transfer(paths, self._dir, move=(mode == "cut"))
        if mode == "cut":
            self._clipboard = None
        self.refresh()

    def _transfer(self, mode: str) -> None:
        from PySide6.QtWidgets import QFileDialog
        paths = self._selected_paths()
        if not paths:
            return
        dest = QFileDialog.getExistingDirectory(
            self, "复制到…" if mode == "copy" else "移动到…", str(self._dir))
        if not dest:
            return
        self._do_transfer(paths, Path(dest), move=(mode == "move"))
        if mode == "move":
            self.refresh()

    def _do_transfer(self, paths: list[Path], dest: Path, move: bool) -> None:
        failed = []
        for p in paths:
            target = dest / p.name
            if target.resolve() == p.resolve():
                continue
            target = self._unique_name(target)
            try:
                shutil.move(str(p), str(target)) if move else shutil.copy2(str(p), str(target))
            except OSError as e:
                failed.append(f"{p.name}: {e}")
        if failed:
            QMessageBox.warning(self, "部分操作失败", "\n".join(failed[:10]))
        else:
            verb = "移动" if move else "复制"
            self._status.showMessage(f"已{verb} {len(paths)} 个文件到 {dest}", 3000)

    @staticmethod
    def _unique_name(target: Path) -> Path:
        if not target.exists():
            return target
        stem, suffix = target.stem, target.suffix
        n = 2
        while True:
            cand = target.with_name(f"{stem} ({n}){suffix}")
            if not cand.exists():
                return cand
            n += 1

    def _reveal(self) -> None:
        path = self._current_path() or self._dir
        try:
            subprocess.Popen(["xdg-open", str(path.parent if path.is_file() else path)])
        except OSError:
            pass

    # ------------------------------------------------------------- 状态栏
    def _update_status(self, *_) -> None:
        total = self._model.rowCount()
        sel = len(self._view.selectionModel().selectedIndexes())
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
        m = QMenu(self)
        m.addAction("查看\tEnter", self._open_current)
        m.addSeparator()
        m.addAction("重命名\tF2", self._rename)
        m.addAction("删除\tDel", self._delete)
        m.addSeparator()
        m.addAction("复制\tCtrl+C", self._copy)
        m.addAction("剪切\tCtrl+X", self._cut)
        m.addAction("复制到…", lambda: self._transfer("copy"))
        m.addAction("移动到…", lambda: self._transfer("move"))
        m.exec(self._view.viewport().mapToGlobal(pos))

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
            self._model.set_thumb_size(edge)
            self._apply_grid()
        key = s.value("sort_key", type=int)
        if key in config.SORT_NAMES:
            self._sort_key = key
        self._sort_reverse = bool(s.value("sort_reverse", False, type=bool))
        self._sort_rev_act.setChecked(self._sort_reverse)

    def closeEvent(self, ev) -> None:
        s = self._settings
        s.setValue("geometry", self.saveGeometry())
        s.setValue("splitter", self._splitter.sizes())
        s.setValue("left_splitter", self._left_splitter.sizes())
        s.setValue("preview_visible", self._preview_act.isChecked())
        s.setValue("thumb_size", self._model.thumb_size())
        s.setValue("sort_key", self._sort_key)
        s.setValue("sort_reverse", self._sort_reverse)
        s.setValue("last_dir", str(self._dir))
        if self._viewer:
            self._viewer.teardown()
        self._preview.shutdown()
        self._loader.shutdown()
        super().closeEvent(ev)


HELP_TEXT = """\
【浏览器】
  Enter / 双击      查看图片
  Backspace         回到上级目录
  F2                重命名
  Del               删除
  Ctrl+C / X / V    复制 / 剪切 / 粘贴到当前目录
  Ctrl+Shift+C / M  复制到… / 移动到…
  Ctrl++ / Ctrl+-   缩略图放大 / 缩小
  F5                刷新
  F9                显示 / 隐藏目录树
  Ctrl+S            从第一张开始全屏幻灯片

【预览窗格】
  菜单「查看 → 预览窗格」显示 / 隐藏选中图片的预览

【看图器】
  空格 / PgDn / →   下一张
  退格 / PgUp / ←   上一张
  Home / End        第一张 / 最后一张
  + / -             放大 / 缩小
  *                 适应窗口
  /                 实际大小 1:1
  W                 适应宽度
  F / Enter / F11   全屏切换
  S                 幻灯片开关
  [ / ]             幻灯片间隔 减 / 加
  I                 显示 / 隐藏信息条
  Del               删除当前图片
  Esc               退出全屏 / 返回浏览

  鼠标：单击翻页，拖拽平移，滚轮翻页，
        Ctrl+滚轮 缩放，中键切换 适应/1:1，双击全屏
"""
