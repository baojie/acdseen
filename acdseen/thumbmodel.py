"""缩略图列表的模型与绘制。

模型只管"有哪些文件、缩略图到了没"，绘制只管"一格长什么样"，
两边都不认识 Browser —— 换个宿主窗口照样能用。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QListView, QStyle, QStyledItemDelegate

from . import config
from .loader import ThumbnailLoader, image_dimensions
from .util import format_mtime, format_size, human_dims


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
