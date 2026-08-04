"""Win95 look: palette, style sheet, and the pitfall that drags Qt into infinite recursion."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QStyle, QStyleOption, QTreeView

from acdseen import config, theme
from acdseen.browser import Browser
from conftest import pump


@pytest.fixture
def win95(qapp):
    theme.apply(qapp, True)
    yield qapp
    theme.apply(qapp, False)


def test_palette_uses_win95_system_colors(win95):
    pal = win95.palette()
    assert pal.color(QPalette.Window).name() == theme.FACE
    assert pal.color(QPalette.Highlight).name() == theme.HILIGHT       # #000080
    assert pal.color(QPalette.HighlightedText).name() == theme.LIGHT
    assert pal.color(QPalette.Base).name() == theme.WINDOW


def test_selection_greys_out_when_unfocused(win95):
    pal = win95.palette()
    assert pal.color(QPalette.Inactive, QPalette.Highlight).name() == theme.SHADOW


def test_stylesheet_is_applied(win95):
    assert theme.FACE in win95.styleSheet()


def test_disabling_the_theme_cleans_up(qapp):
    theme.apply(qapp, True)
    assert qapp.styleSheet()
    theme.apply(qapp, False)
    assert qapp.styleSheet() == ""


def test_drawing_tree_branches_does_not_recurse(win95):
    """Regression: QStyle::proxy() returns the outermost proxy, and the base style
    internally loops back to us. If PE_IndicatorBranch keeps a "fall back to
    super() when not drawn" branch, it stack-overflows."""
    pm = QPixmap(40, 40); pm.fill(Qt.white)
    p = QPainter(pm)
    opt = QStyleOption(); opt.rect = QRect(0, 0, 20, 20)
    for state in (QStyle.State_None,
                  QStyle.State_Item,
                  QStyle.State_Children,
                  QStyle.State_Children | QStyle.State_Open,
                  QStyle.State_Item | QStyle.State_Sibling | QStyle.State_Children):
        opt.state = state
        win95.style().drawPrimitive(QStyle.PE_IndicatorBranch, opt, p)   # must not explode
    p.end()


def test_drawing_scrollbar_arrows_does_not_recurse(win95):
    pm = QPixmap(40, 40); pm.fill(Qt.white)
    p = QPainter(pm)
    opt = QStyleOption(); opt.rect = QRect(0, 0, 16, 16)
    opt.state = QStyle.State_Enabled
    for el in (QStyle.PE_IndicatorArrowUp, QStyle.PE_IndicatorArrowDown,
               QStyle.PE_IndicatorArrowLeft, QStyle.PE_IndicatorArrowRight):
        win95.style().drawPrimitive(el, opt, p)
    p.end()


def test_browser_paints_under_the_win95_theme(win95, workdir):
    b = Browser(workdir)
    b.resize(900, 600)
    b.show()
    pump(win95, 2500)
    for mode in (config.VIEW_LIST, config.VIEW_THUMBS):
        b._set_view_mode(mode)
        pump(win95, 800)
        pm = QPixmap(b.size())
        b.render(pm)                      # actually render it; a bad style sheet blows up here
        assert not pm.isNull()
    b.close()
    pump(win95, 300)


def test_preview_pane_follows_the_palette(win95, workdir):
    """Regression: the preview pane used to hardcode a dark color, leaving an awkward black block under the gray theme."""
    b = Browser(workdir)
    b.resize(900, 600); b.show()
    pump(win95, 2000)
    pv = b._preview
    pm = QPixmap(pv.size()); pv.render(pm)
    img = pm.toImage()
    corner = img.pixelColor(3, 3)
    assert corner.lightness() > 100, f"preview pane still dark: {corner.name()}"
    b.close(); pump(win95, 300)


def test_menu_toggle_switches_both_ways(qapp, workdir):
    b = Browser(workdir)
    b.show(); pump(qapp, 1500)
    b._toggle_win95(True)
    assert b._win95_act.isChecked()
    assert qapp.styleSheet()
    b._toggle_win95(False)
    assert not b._win95_act.isChecked()
    assert qapp.styleSheet() == ""
    b.close(); pump(qapp, 300)
    theme.apply(qapp, False)


# ------------------------------------------------------------------ icons
def test_pixel_grids_are_all_16x16(qapp):
    for name, grid in (("closed", theme.FOLDER_CLOSED),
                       ("open", theme.FOLDER_OPEN),
                       ("drive", theme.DRIVE),
                       ("floppy", theme.FLOPPY),
                       ("cdrom", theme.CDROM),
                       ("network", theme.NETWORK),
                       ("parent", theme.PARENT)):
        assert len(grid) == 16, f"{name} row count is not 16"
        bad = [i for i, row in enumerate(grid) if len(row) != 16]
        assert not bad, f"{name} row {bad} width is not 16"
        unknown = {ch for row in grid for ch in row} - set(theme._ICON_COLORS) - {"."}
        assert not unknown, f"{name} has undefined color characters: {unknown}"


def test_folder_icon_is_yellow(qapp):
    pm = theme.folder_pixmap(16, False)
    img = pm.toImage()
    yellow = sum(1 for y in range(16) for x in range(16)
                 if img.pixelColor(x, y).name() == theme.ICON_FACE)
    assert yellow > 60, f"only {yellow} yellow pixels; the icon is probably wrong"
    assert img.pixelColor(0, 0).alpha() == 0, "the corners must be transparent"


def test_open_and_closed_folders_differ(qapp):
    a = theme.folder_pixmap(16, False).toImage()
    b = theme.folder_pixmap(16, True).toImage()
    assert a != b, "open and closed must be visibly different, or the icon was pointless"


def test_icons_stay_sharp_when_scaled(qapp):
    """Pixel art must only be scaled with nearest-neighbor; one smoothing pass and it's no longer Win95."""
    pm = theme.folder_pixmap(32, False)
    assert pm.size().width() == 32
    colors = {pm.toImage().pixelColor(x, y).name()
              for x in range(32) for y in range(32)
              if pm.toImage().pixelColor(x, y).alpha() > 0}
    allowed = set(theme._ICON_COLORS.values())
    assert colors <= allowed, f"intermediate colors appeared, meaning it was smoothed: {colors - allowed}"


def test_tree_uses_the_win95_icons(win95, workdir):
    from PySide6.QtWidgets import QFileIconProvider
    b = Browser(workdir)
    b.show(); pump(win95, 1500)
    b._toggle_win95(True)
    assert isinstance(b._fs.iconProvider(), theme.Win95IconProvider)
    b._toggle_win95(False)
    assert not isinstance(b._fs.iconProvider(), theme.Win95IconProvider)
    b.close(); pump(win95, 300)


def test_icon_provider_caches(qapp):
    """icon(QFileInfo) is called once per row; without caching, dozens of icons get redrawn every frame."""
    prov = theme.Win95IconProvider()
    a = prov._icon("folder")
    b = prov._icon("folder")
    assert a is b


def test_ui_font_has_antialiasing_off(win95):
    """Win95's UI font is a bitmap font, not a single blurred pixel. With
    antialiasing on, text goes fuzzy and the whole UI instantly looks "modern" --
    this is the single biggest factor for the era feel."""
    from PySide6.QtGui import QFont
    assert theme.ui_font().styleStrategy() == QFont.NoAntialias
    assert win95.font().styleStrategy() == QFont.NoAntialias


def test_drives_get_different_icons_by_type(qapp):
    from PySide6.QtWidgets import QFileIconProvider
    prov = theme.Win95IconProvider()
    drive = prov.icon(QFileIconProvider.Drive).pixmap(16, 16).toImage()
    net = prov.icon(QFileIconProvider.Network).pixmap(16, 16).toImage()
    folder = prov.icon(QFileIconProvider.Folder).pixmap(16, 16).toImage()
    assert drive != net != folder, "the three drive types must not look alike"
