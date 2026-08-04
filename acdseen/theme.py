"""Windows 95 look.

Done the way ACDSee 2.x looked on Win95: #C0C0C0 grey background, every control
gets a 2px beveled border (top-left white / bottom-right dark grey, reversed
when pressed), a full row of #000080 dark-blue selection with white text,
headers that are a row of raised buttons, and scrollbars that are a groove
with square arrow buttons.

Split in two:
  * QPalette + style sheet -- colors and most borders
  * Win95Style            -- what the style sheet can't draw: the tree's
                             +/- boxes and dotted connector lines, scrollbar
                             arrows, the header's beveled ridge. In Qt these
                             are all primitive elements and can only be drawn.

The fullscreen viewer doesn't get this treatment: the original Viewer was pure
black, and putting grey chrome on it would be wrong.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QFileIconProvider, QProxyStyle,
                               QStyle, QStyleFactory)

# Win95's system colors -- none of them can be adjusted
FACE = "#c0c0c0"        # 3D control surface
LIGHT = "#ffffff"       # highlight (top-left outer edge)
SHADOW = "#808080"      # shadow (bottom-right inner edge)
DKSHADOW = "#000000"    # deep shadow (bottom-right outer edge)
WINDOW = "#ffffff"      # document area background
TEXT = "#000000"
HILIGHT = "#000080"     # the navy blue selection bar
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
    p.setColor(QPalette.ToolTipBase, c("#ffffe1"))    # the famous pale-yellow tooltip
    p.setColor(QPalette.ToolTipText, c(TEXT))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c(GRAYTEXT))
    # the selection bar turns grey when unfocused -- that's how Win95 did it
    p.setColor(QPalette.Inactive, QPalette.Highlight, c(SHADOW))
    p.setColor(QPalette.Inactive, QPalette.HighlightedText, c(LIGHT))
    return p


QSS = f"""
QMainWindow, QWidget {{
    background: {FACE};
    color: {TEXT};
}}

/* document area: white + sunken border, the Win95 mark of "editable content" */
QListView, QTreeView, QAbstractScrollArea {{
    background: {WINDOW};
    border: 2px solid {FACE};
    border-top-color: {SHADOW};
    border-left-color: {SHADOW};
    border-right-color: {LIGHT};
    border-bottom-color: {LIGHT};
}}
QListView::item {{ border: 0; padding: 0px 2px; }}
/* list vertical separator: the original had a light grey line between every column, running the full height */
QTreeView::item {{
    border: 0;
    border-right: 1px solid #d4d0c8;
    padding: 0px 2px;
}}
QListView::item:selected, QTreeView::item:selected {{
    background: {HILIGHT};
    color: {HILIGHT_TEXT};
}}

/* header: a row of raised buttons with a dark bevel on the right and bottom */
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

/* menu bar: flat; only raises or sinks when hovered or opened */
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

/* status bar: sunken segment */
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

/* scrollbar: square groove + raised handle; the arrows are drawn by Win95Style */
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

/* splitter: just a patch of grey, no handle */
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
/* path bar: sunken input + a raised drop-down button at the right end */
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
    """Paints the few primitives the style sheet can't handle."""

    # These elements must be taken over "unconditionally" and must never fall
    # back to super(): QStyle::proxy() returns the outermost proxy, and when the
    # base style draws sub-widgets internally it routes back here through it;
    # if an element had a fallback branch it would recurse infinitely.
    _OWNED = None      # lazy init, see drawPrimitive

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

    # -- the tree's +/- boxes and dotted lines --
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
        # dotted line: Win95 dots every other pixel, not Qt's default DashLine
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
            painter.drawLine(x + 2, cy, x + box - 3, cy)          # horizontal bar
            if not (state & QStyle.StateFlag.State_Open):
                painter.drawLine(cx, y + 2, cx, y + box - 3)      # vertical bar -> becomes a +
        painter.restore()

    # -- the solid little triangle on scrollbars --
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


# ---------------------------------------------------------------- icons
# Win95 icons use only a handful of colors: black outline, bright yellow face, olive shadow, white highlight.
ICON_OUTLINE = "#000000"
ICON_FACE = "#ffff00"
ICON_SHADE = "#808000"
ICON_HILITE = "#ffffff"
ICON_GRAY = "#c0c0c0"
ICON_DKGRAY = "#808080"


# Icons are defined pixel by pixel, not drawn. On a canvas as small as 16x16,
# a polygon's diagonal edge is only two or three pixels long, so a bevel is
# unreadable and just smears into a black blob; the artists of that era also
# placed them one cell at a time. Character meanings: k black outline /
# w white highlight / y bright yellow / o olive shadow /
#              g grey / d dark grey / l green indicator light / . transparent
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

# Open: the back sheet stays standing while the front sheet slides down one
# cell at a time toward the bottom-left, so the top-right corner pokes out and
# the bottom-left corner sticks out; that diagonal carries all the visual
# information "open" needs.
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

# the "parent directory" icon in the first row of the list: a folder lying on its side, easier to recognize than two dots
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
    ".kgddddddggggdk.",     # the front-panel slot, otherwise a grey panel on a grey background looks empty
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
    """Dot out 16x16 at 1:1, then upscale by an integer factor with nearest-
    neighbor. Scaling must never be smooth -- blurring would ruin it."""
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
    """Win95's yellow folder."""
    return _from_grid(FOLDER_OPEN if is_open else FOLDER_CLOSED, size)


def drive_pixmap(size: int = 16) -> QPixmap:
    """A grey box with a green light -- Win95's hard drive icon."""
    return _from_grid(DRIVE, size)


def parent_pixmap(size: int = 16) -> QPixmap:
    """The "parent directory" icon in the first row of the list."""
    return _from_grid(PARENT, size)


class Win95IconProvider(QFileIconProvider):
    """Replaces the directory tree's system icons with hand-drawn Win95 icons.

    QFileSystemModel picks up its icons from here, so swapping the provider
    changes the whole tree. Icons are cached by size -- icon(QFileInfo) is
    called once per row.
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
            # use the same pixmap for selected / disabled states; don't let Qt recolor it grey on its own
            hit.addPixmap(pm, QIcon.Selected)
            hit.addPixmap(pm, QIcon.Disabled)
            self._cache[key] = hit
        return hit

    _BY_TYPE = None      # lazy table: IconType is an enum, building the table at import time would slow startup

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
        # QFileInfo overload -- the vast majority of tree calls go through this branch
        if arg.isDir():
            name = arg.fileName().lower()
            # Linux has no drive letters, so guess from the mount point name; fall back to a folder
            if name in ("floppy", "fd0", "fd1"):
                return self._icon("floppy")
            if name in ("cdrom", "dvd", "sr0", "cdrom0"):
                return self._icon("cdrom")
            return self._icon("folder")
        return super().icon(arg)


def ui_font() -> QFont:
    """A stand-in for MS Sans Serif. Use the real thing if a Windows font is
    installed, otherwise fall back to a small sans-serif."""
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
    # Win95's UI font was a bitmap font, not a single blurred pixel. With
    # antialiasing the text goes fuzzy and the whole UI instantly feels
    # "modern" -- this is the easiest detail to overlook yet the one that most
    # affects the period feel.
    f.setStyleStrategy(QFont.NoAntialias)
    f.setHintingPreference(QFont.PreferFullHinting)
    return f


def apply(app: QApplication, on: bool) -> None:
    """Toggle the Win95 look. Turning it off restores Qt's own default style."""
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
