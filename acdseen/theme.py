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
from PySide6.QtGui import QColor, QFont, QPalette, QPen
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleFactory

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
    f.setStyleStrategy(QFont.PreferDefault)
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
