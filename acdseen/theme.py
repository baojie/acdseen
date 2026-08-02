"""Windows 95 外观。

照着 ACDSee 2.x 在 Win95 上的样子做：#C0C0C0 灰底，控件一律 2px 立体边框
（左上白 / 右下深灰，凹陷时反过来），整行 #000080 深蓝选中配白字，表头是
一排凸起的按钮，滚动条是带方块箭头的槽。

分两半：
  * QPalette + 样式表 —— 颜色和大部分边框
  * Win95Style       —— 样式表画不了的东西：树的 +/- 方框与虚线连接线、
                        滚动条箭头、表头的立体棱。这些在 Qt 里都是
                        primitive element，只能画。

全屏看图器不套这一层：原版 Viewer 就是纯黑铺满，套上灰边反而不对。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QFileIconProvider, QProxyStyle,
                               QStyle, QStyleFactory)

# Win95 的那套系统色，一个都不能调
FACE = "#c0c0c0"        # 3D 控件表面
LIGHT = "#ffffff"       # 高光（左上外沿）
SHADOW = "#808080"      # 阴影（右下内沿）
DKSHADOW = "#000000"    # 深阴影（右下外沿）
WINDOW = "#ffffff"      # 文档区底色
TEXT = "#000000"
HILIGHT = "#000080"     # 选中条那个海军蓝
HILIGHT_TEXT = "#ffffff"
GRAYTEXT = "#808080"


def win95_palette() -> QPalette:
    p = QPalette()
    c = QColor
    p.setColor(QPalette.Window, c(FACE))
    p.setColor(QPalette.WindowText, c(TEXT))
    p.setColor(QPalette.Base, c(WINDOW))
    p.setColor(QPalette.AlternateBase, c(FACE))
    p.setColor(QPalette.Text, c(TEXT))
    p.setColor(QPalette.Button, c(FACE))
    p.setColor(QPalette.ButtonText, c(TEXT))
    p.setColor(QPalette.Highlight, c(HILIGHT))
    p.setColor(QPalette.HighlightedText, c(HILIGHT_TEXT))
    p.setColor(QPalette.Light, c(LIGHT))
    p.setColor(QPalette.Midlight, c(FACE))
    p.setColor(QPalette.Mid, c(SHADOW))
    p.setColor(QPalette.Dark, c(SHADOW))
    p.setColor(QPalette.Shadow, c(DKSHADOW))
    p.setColor(QPalette.ToolTipBase, c("#ffffe1"))    # 那个著名的淡黄提示框
    p.setColor(QPalette.ToolTipText, c(TEXT))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c(GRAYTEXT))
    # 失焦时选中条变灰 —— Win95 就是这么干的
    p.setColor(QPalette.Inactive, QPalette.Highlight, c(SHADOW))
    p.setColor(QPalette.Inactive, QPalette.HighlightedText, c(LIGHT))
    return p


QSS = f"""
QMainWindow, QWidget {{
    background: {FACE};
    color: {TEXT};
}}

/* 文档区：白底 + 凹陷边框，这是 Win95 里"可编辑内容"的标志 */
QListView, QTreeView, QAbstractScrollArea {{
    background: {WINDOW};
    border: 2px solid {FACE};
    border-top-color: {SHADOW};
    border-left-color: {SHADOW};
    border-right-color: {LIGHT};
    border-bottom-color: {LIGHT};
}}
QListView::item {{ border: 0; padding: 0px 2px; }}
/* 列表的竖分隔线：原版每列之间都有一道浅灰，一直贯到底 */
QTreeView::item {{
    border: 0;
    border-right: 1px solid #d4d0c8;
    padding: 0px 2px;
}}
QListView::item:selected, QTreeView::item:selected {{
    background: {HILIGHT};
    color: {HILIGHT_TEXT};
}}

/* 表头：一排凸起的按钮，右边和下边留深棱 */
QHeaderView {{
    background: {FACE};
    border: 0;
}}
QHeaderView::section {{
    background: {FACE};
    color: {TEXT};
    padding: 2px 4px;
    border: 1px solid {FACE};
    border-top-color: {LIGHT};
    border-left-color: {LIGHT};
    border-right-color: {DKSHADOW};
    border-bottom-color: {DKSHADOW};
}}
QHeaderView::section:pressed {{
    border-top-color: {SHADOW};
    border-left-color: {SHADOW};
    border-right-color: {LIGHT};
    border-bottom-color: {LIGHT};
    padding: 3px 3px 1px 5px;
}}

/* 菜单栏：平的，只有划过和展开时才凸/凹 */
QMenuBar {{
    background: {FACE};
    border-bottom: 1px solid {FACE};
    padding: 1px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 3px 8px;
}}
QMenuBar::item:selected {{
    background: {HILIGHT};
    color: {HILIGHT_TEXT};
}}
QMenu {{
    background: {FACE};
    border: 2px solid {FACE};
    border-top-color: {LIGHT};
    border-left-color: {LIGHT};
    border-right-color: {DKSHADOW};
    border-bottom-color: {DKSHADOW};
    padding: 2px;
}}
QMenu::item {{
    padding: 3px 26px 3px 22px;
}}
QMenu::item:selected {{
    background: {HILIGHT};
    color: {HILIGHT_TEXT};
}}
QMenu::item:disabled {{ color: {GRAYTEXT}; }}
QMenu::separator {{
    height: 2px;
    margin: 3px 2px;
    border-top: 1px solid {SHADOW};
    border-bottom: 1px solid {LIGHT};
}}
QMenu::indicator {{ width: 12px; height: 12px; margin-left: 4px; }}

/* 状态栏：凹陷的分格 */
QStatusBar {{
    background: {FACE};
    border-top: 1px solid {LIGHT};
}}
QStatusBar QLabel {{
    border: 1px solid {SHADOW};
    border-right-color: {LIGHT};
    border-bottom-color: {LIGHT};
    padding: 1px 4px;
}}
QStatusBar::item {{ border: 0; }}

/* 滚动条：方槽 + 凸起滑块，箭头交给 Win95Style 画 */
QScrollBar:vertical, QScrollBar:horizontal {{
    background: #dfdfdf;
    border: 0;
}}
QScrollBar:vertical {{ width: 16px; }}
QScrollBar:horizontal {{ height: 16px; }}
QScrollBar::handle {{
    background: {FACE};
    border: 1px solid {FACE};
    border-top-color: {LIGHT};
    border-left-color: {LIGHT};
    border-right-color: {DKSHADOW};
    border-bottom-color: {DKSHADOW};
}}
QScrollBar::handle:vertical {{ min-height: 16px; }}
QScrollBar::handle:horizontal {{ min-width: 16px; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    background: {FACE};
    border: 1px solid {FACE};
    border-top-color: {LIGHT};
    border-left-color: {LIGHT};
    border-right-color: {DKSHADOW};
    border-bottom-color: {DKSHADOW};
    subcontrol-origin: margin;
}}
QScrollBar::add-line:vertical {{ height: 16px; subcontrol-position: bottom; }}
QScrollBar::sub-line:vertical {{ height: 16px; subcontrol-position: top; }}
QScrollBar::add-line:horizontal {{ width: 16px; subcontrol-position: right; }}
QScrollBar::sub-line:horizontal {{ width: 16px; subcontrol-position: left; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: #dfdfdf; }}

/* 分割条：就是一片灰，没有把手 */
QSplitter::handle {{ background: {FACE}; }}

QPushButton {{
    background: {FACE};
    border: 2px solid {FACE};
    border-top-color: {LIGHT};
    border-left-color: {LIGHT};
    border-right-color: {DKSHADOW};
    border-bottom-color: {DKSHADOW};
    padding: 4px 12px;
    min-width: 68px;
}}
QPushButton:pressed {{
    border-top-color: {DKSHADOW};
    border-left-color: {DKSHADOW};
    border-right-color: {LIGHT};
    border-bottom-color: {LIGHT};
}}
QLineEdit {{
    background: {WINDOW};
    border: 2px solid {FACE};
    border-top-color: {SHADOW};
    border-left-color: {SHADOW};
    border-right-color: {LIGHT};
    border-bottom-color: {LIGHT};
    padding: 2px;
}}
/* 路径栏：凹陷输入框 + 右端一个凸起的下拉按钮 */
QComboBox {{
    background: {WINDOW};
    border: 2px solid {FACE};
    border-top-color: {SHADOW};
    border-left-color: {SHADOW};
    border-right-color: {LIGHT};
    border-bottom-color: {LIGHT};
    padding: 1px 2px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 16px;
    background: {FACE};
    border: 1px solid {FACE};
    border-top-color: {LIGHT};
    border-left-color: {LIGHT};
    border-right-color: {DKSHADOW};
    border-bottom-color: {DKSHADOW};
}}
QComboBox QAbstractItemView {{
    background: {WINDOW};
    border: 1px solid {DKSHADOW};
    selection-background-color: {HILIGHT};
    selection-color: {HILIGHT_TEXT};
}}
QToolTip {{
    background: #ffffe1;
    color: {TEXT};
    border: 1px solid {DKSHADOW};
    padding: 2px;
}}
"""


class Win95Style(QProxyStyle):
    """补样式表画不了的几处 primitive。"""

    # 这几个 element 必须"无条件"接管，绝不能回退到 super()：QStyle::proxy()
    # 返回的是最外层代理，基础样式内部画子部件时会通过它绕回这里，同一个
    # element 一旦有回退分支就会无限递归。
    _OWNED = None      # 延迟初始化，见 drawPrimitive

    def drawPrimitive(self, element, opt, painter, widget=None) -> None:
        pe = QStyle.PrimitiveElement
        if Win95Style._OWNED is None:
            Win95Style._OWNED = {
                pe.PE_IndicatorBranch, pe.PE_IndicatorArrowUp,
                pe.PE_IndicatorArrowDown, pe.PE_IndicatorArrowLeft,
                pe.PE_IndicatorArrowRight,
            }
        if element == pe.PE_IndicatorBranch:
            self._draw_branch(opt, painter)
            return
        if element in Win95Style._OWNED:
            self._draw_arrow(element, opt, painter)
            return
        super().drawPrimitive(element, opt, painter, widget)

    # -- 目录树的 +/- 方框与虚线 --
    def _draw_branch(self, opt, painter) -> None:
        r = opt.rect
        state = opt.state
        has_children = bool(state & QStyle.StateFlag.State_Children)
        has_sibling = bool(state & QStyle.StateFlag.State_Sibling)
        is_item = bool(state & QStyle.StateFlag.State_Item)
        if not (has_children or has_sibling or is_item):
            return

        cx, cy = r.center().x() + 1, r.center().y() + 1
        painter.save()
        # 虚线：Win95 是隔像素点一个点，不是 Qt 默认的 DashLine
        pen = QPen(QColor(SHADOW)); pen.setStyle(Qt.DotLine)
        painter.setPen(pen)
        if is_item:
            painter.drawLine(cx, cy, r.right(), cy)
            painter.drawLine(cx, r.top(), cx, cy)
        if has_sibling:
            painter.drawLine(cx, cy if is_item else r.top(), cx, r.bottom())

        if has_children:
            painter.setPen(QColor(SHADOW))
            painter.setBrush(QColor(WINDOW))
            box = 9
            x, y = cx - box // 2, cy - box // 2
            painter.drawRect(x, y, box - 1, box - 1)
            painter.setPen(QColor(TEXT))
            painter.drawLine(x + 2, cy, x + box - 3, cy)          # 横杠
            if not (state & QStyle.StateFlag.State_Open):
                painter.drawLine(cx, y + 2, cx, y + box - 3)      # 竖杠 → 变成 +
        painter.restore()

    # -- 滚动条上那种实心小三角 --
    def _draw_arrow(self, element, opt, painter) -> None:
        pe = QStyle.PrimitiveElement
        r = opt.rect
        cx, cy = r.center().x() + 1, r.center().y() + 1
        n = 4
        pts = {
            pe.PE_IndicatorArrowUp:    [QPoint(cx, cy - n + 1), QPoint(cx - n, cy + 2), QPoint(cx + n, cy + 2)],
            pe.PE_IndicatorArrowDown:  [QPoint(cx, cy + n - 1), QPoint(cx - n, cy - 2), QPoint(cx + n, cy - 2)],
            pe.PE_IndicatorArrowLeft:  [QPoint(cx - n + 1, cy), QPoint(cx + 2, cy - n), QPoint(cx + 2, cy + n)],
            pe.PE_IndicatorArrowRight: [QPoint(cx + n - 1, cy), QPoint(cx - 2, cy - n), QPoint(cx - 2, cy + n)],
        }[element]
        painter.save()
        enabled = bool(opt.state & QStyle.StateFlag.State_Enabled)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(TEXT if enabled else GRAYTEXT))
        painter.drawPolygon(pts)
        painter.restore()


# ---------------------------------------------------------------- 图标
# Win95 图标的全部用色就这几个：黑描边、亮黄面、橄榄色阴影、白高光。
ICON_OUTLINE = "#000000"
ICON_FACE = "#ffff00"
ICON_SHADE = "#808000"
ICON_HILITE = "#ffffff"
ICON_GRAY = "#c0c0c0"
ICON_DKGRAY = "#808080"


# 图标是逐像素定义的，不是画出来的。16×16 这么小的画布上，多边形的斜边
# 只有两三像素，斜面根本读不出来，反而会糊成一坨黑；当年的美工也是一格一格
# 点的。字符含义：k 黑描边 / w 白高光 / y 亮黄 / o 橄榄阴影 /
#              g 灰 / d 深灰 / l 绿色指示灯 / . 透明
_ICON_COLORS = {
    "k": ICON_OUTLINE, "w": ICON_HILITE, "y": ICON_FACE, "o": ICON_SHADE,
    "g": ICON_GRAY, "d": ICON_DKGRAY, "l": "#00c000", "b": "#000080",
}

FOLDER_CLOSED = (
    "................",
    "................",
    ".kkkkk..........",
    ".kwwwwk.........",
    ".kwyyyykkkkkkk..",
    ".kwyyyyyyyyyyyk.",
    ".kwyyyyyyyyyyyk.",
    ".kwyyyyyyyyyyyk.",
    ".kwyyyyyyyyyyyk.",
    ".kwyyyyyyyyyyyk.",
    ".kwyyyyyyyyyyyk.",
    ".kwyyyyyyyyyyok.",
    ".kooooooooooook.",
    ".kkkkkkkkkkkkkk.",
    "................",
    "................",
)

# 打开：后片照旧立着，前片整体向左下错开一格一格地落下来，
# 于是右上角探出、左下角伸出，那道斜面就是"打开"的全部视觉信息。
FOLDER_OPEN = (
    "................",
    "................",
    ".kkkkk..........",
    ".kwwwwk.........",
    ".kwyyyykkkkkkk..",
    ".kwyyyyyyyyyyyk.",
    ".kwyyyyyyyyyyyk.",
    ".kwyyyyyyyyyyyk.",
    "..kkkkkkkkkkkkkk",
    "..kyyyyyyyyyyyk.",
    ".kyyyyyyyyyyyk..",
    ".kyyyyyyyyyyk...",
    "kyyyyyyyyyyk....",
    "kkkkkkkkkkk.....",
    "................",
    "................",
)

FLOPPY = (
    "................",
    "................",
    "................",
    ".kkkkkkkkkkkkkk.",
    ".kgggggggggggdk.",
    ".kgkkkkkkkkgggdk",
    ".kgkwwwwwwkgggdk",
    ".kgkwwwwwwkgggdk",
    ".kgkkkkkkkkgggdk",
    ".kgggggggggggdk.",
    ".kgkkkkkkkkkgdk.",
    ".kgkddddddddkdk.",
    ".kkkkkkkkkkkkkk.",
    "................",
    "................",
    "................",
)

CDROM = (
    "................",
    "................",
    "................",
    "................",
    ".kkkkkkkkkkkkkk.",
    ".kwwwwwwwwwwwwk.",
    ".kggggkkkkgggdk.",
    ".kgggkwwwwkggdk.",
    ".kgggkwkkwkggdk.",
    ".kglgkwwwwkggdk.",
    ".kddddkkkkdddddk",
    ".kkkkkkkkkkkkkk.",
    "................",
    "................",
    "................",
    "................",
)

NETWORK = (
    "................",
    "..kkkkkkkk......",
    "..kwwwwwwk......",
    "..kwbbbbwk......",
    "..kwbbbbwk......",
    "..kkkkkkkk......",
    "....kggk........",
    "..kkkkkkkkkk....",
    "..k......kkkk...",
    "..k...kkkkkkkk..",
    "kkkkkkkkwwwwwk..",
    "kwwwwwwkwbbbwk..",
    "kwbbbbwkwwwwwk..",
    "kwwwwwwkkkkkkk..",
    "kkkkkkkk........",
    "................",
)

# 列表第一行那个"上级目录"图标：一个横躺的文件夹，比 .. 两个点好认
PARENT = (
    "................",
    "................",
    "................",
    "................",
    "................",
    ".kkkkkk.........",
    ".kwwwwkkkkkkkkk.",
    ".kwyyyyyyyyyyyk.",
    ".kwyyyyyyyyyyok.",
    ".kooooooooooook.",
    ".kkkkkkkkkkkkkk.",
    "................",
    "................",
    "................",
    "................",
    "................",
)

DRIVE = (
    "................",
    "................",
    "................",
    "................",
    ".kkkkkkkkkkkkkk.",
    ".kwwwwwwwwwwwwk.",
    ".kgggggggggggdk.",
    ".kgddddddggggdk.",     # 前面板的插槽，不然灰底上一片灰看着是空的
    ".kgggggggggggdk.",
    ".kglgggggggggdk.",
    ".kddddddddddddk.",
    ".kkkkkkkkkkkkkk.",
    "................",
    "................",
    "................",
    "................",
)


def _from_grid(grid: tuple[str, ...], size: int = 16) -> QPixmap:
    """按 1:1 点出 16×16，再整数倍最近邻放大 —— 缩放绝不能平滑，一糊就废。"""
    base = QPixmap(16, 16)
    base.fill(Qt.transparent)
    p = QPainter(base)
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            color = _ICON_COLORS.get(ch)
            if color:
                p.fillRect(x, y, 1, 1, QColor(color))
    p.end()
    if size == 16:
        return base
    return base.scaled(size, size, Qt.KeepAspectRatio, Qt.FastTransformation)


def folder_pixmap(size: int = 16, is_open: bool = False) -> QPixmap:
    """Win95 的黄文件夹。"""
    return _from_grid(FOLDER_OPEN if is_open else FOLDER_CLOSED, size)


def drive_pixmap(size: int = 16) -> QPixmap:
    """灰盒子加一颗绿灯，Win95 的硬盘图标。"""
    return _from_grid(DRIVE, size)


def parent_pixmap(size: int = 16) -> QPixmap:
    """列表第一行的"上级目录"图标。"""
    return _from_grid(PARENT, size)


class Win95IconProvider(QFileIconProvider):
    """把目录树的系统图标换成手画的 Win95 图标。

    QFileSystemModel 会拿这里的图标，所以只要换掉 provider，整棵树就变了。
    图标按尺寸缓存 —— icon(QFileInfo) 每一行都会调一次。
    """

    def __init__(self):
        super().__init__()
        self._cache: dict[tuple[str, int], QIcon] = {}

    def _icon(self, kind: str, size: int = 16) -> QIcon:
        key = (kind, size)
        hit = self._cache.get(key)
        if hit is None:
            maker = {"folder": lambda: folder_pixmap(size, False),
                     "open": lambda: folder_pixmap(size, True),
                     "drive": lambda: _from_grid(DRIVE, size),
                     "floppy": lambda: _from_grid(FLOPPY, size),
                     "cdrom": lambda: _from_grid(CDROM, size),
                     "network": lambda: _from_grid(NETWORK, size),
                     "parent": lambda: _from_grid(PARENT, size)}[kind]
            pm = maker()
            hit = QIcon(pm)
            # 选中 / 禁用状态都用同一张，别让 Qt 自作主张把它变灰
            hit.addPixmap(pm, QIcon.Selected)
            hit.addPixmap(pm, QIcon.Disabled)
            self._cache[key] = hit
        return hit

    _BY_TYPE = None      # 延迟建表：IconType 是枚举，导入期建表会拖慢启动

    def icon(self, arg):
        if Win95IconProvider._BY_TYPE is None:
            t = QFileIconProvider
            Win95IconProvider._BY_TYPE = {
                t.Computer: "drive", t.Drive: "drive", t.Desktop: "folder",
                t.Folder: "folder", t.Network: "network", t.Trashcan: "folder",
            }
        if isinstance(arg, QFileIconProvider.IconType):
            kind = Win95IconProvider._BY_TYPE.get(arg)
            return self._icon(kind) if kind else super().icon(arg)
        # QFileInfo 重载 —— 树里绝大多数走这一支
        if arg.isDir():
            name = arg.fileName().lower()
            # Linux 上没有盘符，只能按挂载点名字猜个大概；猜不中就用文件夹
            if name in ("floppy", "fd0", "fd1"):
                return self._icon("floppy")
            if name in ("cdrom", "dvd", "sr0", "cdrom0"):
                return self._icon("cdrom")
            return self._icon("folder")
        return super().icon(arg)


def ui_font() -> QFont:
    """MS Sans Serif 的替身。装了 Win 字体就用真的，没有就退到无衬线小字号。"""
    from PySide6.QtGui import QFontDatabase
    families = set(QFontDatabase.families())
    for name in ("MS Sans Serif", "Microsoft Sans Serif", "Tahoma",
                 "DejaVu Sans", "Liberation Sans"):
        if name in families:
            f = QFont(name, 9)
            break
    else:
        f = QFont()
        f.setPointSize(9)
    # Win95 的界面字体是位图字体，一个像素都不糊。开着抗锯齿字就发虚，
    # 整个界面立刻"现代"了 —— 这是最容易被忽略却最影响年代感的一处。
    f.setStyleStrategy(QFont.NoAntialias)
    f.setHintingPreference(QFont.PreferFullHinting)
    return f


def apply(app: QApplication, on: bool) -> None:
    """开关 Win95 外观。关掉就还原成 Qt 自己的默认样式。"""
    if on:
        base = QStyleFactory.create("Fusion") or app.style()
        app.setStyle(Win95Style(base))
        app.setPalette(win95_palette())
        app.setFont(ui_font())
        app.setStyleSheet(QSS)
    else:
        app.setStyleSheet("")
        app.setStyle(QStyleFactory.create("Fusion") or app.style())
        app.setPalette(QApplication.style().standardPalette())
