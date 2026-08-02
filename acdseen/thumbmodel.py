"""图片列表的模型与缩略图格子的绘制。

模型是多列的（名称 / 尺寸 / 大小 / 类型 / 修改日期），两个视图共用它：
  * 缩略图模式  QListView 只显示第 0 列，走 ThumbDelegate 自己画格子
  * 列表模式    QTreeView 显示全部列，表头、点击排序、拖列宽都是原生的

两边不认识 Browser —— 换个宿主窗口照样能用。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QListView, QStyle, QStyledItemDelegate

from . import config
from .loader import ThumbnailLoader
from .util import format_mtime, format_size, human_dims, image_size

# (标题, 点表头时用的排序键, 默认列宽)。列宽 None = 名称列，占掉剩下的空间。
COLUMNS = (
    ("名称",     config.SORT_NAME,   None),
    ("尺寸",     config.SORT_PIXELS, 110),
    ("大小",     config.SORT_SIZE,    90),
    ("类型",     config.SORT_TYPE,    70),
    ("修改日期", config.SORT_DATE,   140),
)
COL_NAME, COL_DIMS, COL_SIZE, COL_TYPE, COL_MTIME = range(len(COLUMNS))


class ThumbModel(QAbstractTableModel):
    """图片列表模型。缩略图按需异步加载 —— Qt 只为可见项调 data()，
    所以这里的 lazy request 天然只处理视口内的文件。"""

    def __init__(self, loader: ThumbnailLoader, parent=None):
        super().__init__(parent)
        self._parent_dir: Path | None = None   # 有值时第 0 行是 ".."
        self._paths: list[Path] = []
        self._thumbs: dict[Path, QIcon] = {}
        self._requested: set[Path] = set()
        self._edge = config.DEFAULT_THUMB_SIZE
        self._loader = loader
        self._loader.ready.connect(self._on_thumb)
        self._placeholder = self._make_placeholder(self._edge)
        self._parent_pm: QIcon | None = None

    # -- 数据 --
    # 视图里的行 = [".." 导航行（可选）] + 图片行。
    # 对外一律用"视图行号"，内部 _paths 只装图片 —— 两套编号靠 _offset 换算，
    # 别让哨兵路径混进 _paths，否则删除 / 幻灯片 / 预览全要额外判空。
    def set_paths(self, paths: list[Path], parent_dir: Path | None = None) -> None:
        self.beginResetModel()
        self._paths = paths
        self._parent_dir = parent_dir
        self._thumbs.clear()
        self._requested.clear()
        self.endResetModel()

    def _offset(self) -> int:
        return 1 if self._parent_dir is not None else 0

    def parent_dir(self) -> Path | None:
        return self._parent_dir

    def is_parent_row(self, index: QModelIndex) -> bool:
        return bool(index.isValid() and self._offset() and index.row() == 0)

    def image_index(self, index: QModelIndex) -> int:
        """视图行 → _paths 里的下标。导航行或越界返回 -1。"""
        if not index.isValid():
            return -1
        row = index.row() - self._offset()
        return row if 0 <= row < len(self._paths) else -1

    def first_image_row(self) -> int:
        """第一张图在视图里的行号 —— 切目录后该选中的就是它，不是 ".."。"""
        return self._offset() if self._paths else -1

    def paths(self) -> list[Path]:
        return self._paths

    def path_at(self, index: QModelIndex) -> Path | None:
        """只看行号 —— 列表模式下点在哪一列都该拿到同一个文件。
        导航行返回 None：它不是图片，不该进选择集、预览和文件操作。"""
        row = self.image_index(index)
        return self._paths[row] if row >= 0 else None

    def index_of(self, path: Path) -> int:
        """返回视图行号（已含导航行的偏移），找不到是 -1。"""
        try:
            return self._paths.index(path) + self._offset()
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
        self._parent_pm = None
        self._thumbs.clear()
        self._requested.clear()
        self._loader.invalidate()
        self.beginResetModel()
        self.endResetModel()

    def thumb_size(self) -> int:
        return self._edge

    # -- QAbstractTableModel --
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._paths) + self._offset()

    def image_count(self) -> int:
        """图片张数，不含导航行 —— 状态栏要报的是这个。"""
        return len(self._paths)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(COLUMNS):
                return COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if self.is_parent_row(index):
            if role == Qt.DisplayRole:
                return ".." if index.column() == COL_NAME else ""
            if role == Qt.DecorationRole and index.column() == COL_NAME:
                return self._parent_icon()
            if role == Qt.ToolTipRole:
                return f"上级目录：{self._parent_dir}"
            return None

        path = self.path_at(index)
        if path is None:
            return None
        col = index.column()

        if role == Qt.DisplayRole:
            return self._cell(path, col)
        if role == Qt.DecorationRole and col == COL_NAME:
            icon = self._thumbs.get(path)
            if icon is not None:
                return icon
            if path not in self._requested:
                self._requested.add(path)
                self._loader.request(path, self._edge)
            return self._placeholder
        if role == Qt.ToolTipRole:
            return self._tooltip(path)
        if role == Qt.TextAlignmentRole and col in (COL_DIMS, COL_SIZE):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def _cell(self, path: Path, col: int) -> str:
        if col == COL_NAME:
            return path.name
        if col == COL_DIMS:
            w, h = image_size(path)          # 带缓存，滚动不会反复读文件头
            return f"{w}×{h}" if w and h else ""
        if col == COL_TYPE:
            return path.suffix.lstrip(".").upper()
        try:
            st = path.stat()
        except OSError:
            return ""
        if col == COL_SIZE:
            return format_size(st.st_size)
        if col == COL_MTIME:
            return format_mtime(st.st_mtime)
        return ""

    def _parent_icon(self) -> QIcon:
        if self._parent_pm is None:
            from .theme import parent_pixmap
            self._parent_pm = QIcon(parent_pixmap(max(16, min(self._edge, 48))))
        return self._parent_pm

    def _tooltip(self, path: Path) -> str:
        parts = [path.name]
        try:
            st = path.stat()
            parts.append(f"{format_size(st.st_size)}   {format_mtime(st.st_mtime)}")
        except OSError:
            pass
        w, h = image_size(path)
        if w and h:
            parts.append(human_dims(w, h))
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
        # index_of 返回的已经是视图行号，别再加一次偏移
        idx = self.index(row, COL_NAME)
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
