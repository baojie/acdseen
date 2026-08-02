"""Win95 外观：调色板、样式表、以及那个会把 Qt 拖进无限递归的坑。"""

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


def test_调色板用的是win95系统色(win95):
    pal = win95.palette()
    assert pal.color(QPalette.Window).name() == theme.FACE
    assert pal.color(QPalette.Highlight).name() == theme.HILIGHT       # #000080
    assert pal.color(QPalette.HighlightedText).name() == theme.LIGHT
    assert pal.color(QPalette.Base).name() == theme.WINDOW


def test_失焦时选中条变灰(win95):
    pal = win95.palette()
    assert pal.color(QPalette.Inactive, QPalette.Highlight).name() == theme.SHADOW


def test_样式表装上了(win95):
    assert theme.FACE in win95.styleSheet()


def test_关掉外观会清干净(qapp):
    theme.apply(qapp, True)
    assert qapp.styleSheet()
    theme.apply(qapp, False)
    assert qapp.styleSheet() == ""


def test_画树的分支不会无限递归(win95):
    """回归：QStyle::proxy() 返回最外层代理，基础样式内部会绕回我们这里。
    PE_IndicatorBranch 一旦留了"没画就回退 super()"的分支就会栈溢出。"""
    pm = QPixmap(40, 40); pm.fill(Qt.white)
    p = QPainter(pm)
    opt = QStyleOption(); opt.rect = QRect(0, 0, 20, 20)
    for state in (QStyle.State_None,
                  QStyle.State_Item,
                  QStyle.State_Children,
                  QStyle.State_Children | QStyle.State_Open,
                  QStyle.State_Item | QStyle.State_Sibling | QStyle.State_Children):
        opt.state = state
        win95.style().drawPrimitive(QStyle.PE_IndicatorBranch, opt, p)   # 不该炸
    p.end()


def test_画滚动条箭头不会无限递归(win95):
    pm = QPixmap(40, 40); pm.fill(Qt.white)
    p = QPainter(pm)
    opt = QStyleOption(); opt.rect = QRect(0, 0, 16, 16)
    opt.state = QStyle.State_Enabled
    for el in (QStyle.PE_IndicatorArrowUp, QStyle.PE_IndicatorArrowDown,
               QStyle.PE_IndicatorArrowLeft, QStyle.PE_IndicatorArrowRight):
        win95.style().drawPrimitive(el, opt, p)
    p.end()


def test_浏览器在win95外观下能正常绘制(win95, workdir):
    b = Browser(workdir)
    b.resize(900, 600)
    b.show()
    pump(win95, 2500)
    for mode in (config.VIEW_LIST, config.VIEW_THUMBS):
        b._set_view_mode(mode)
        pump(win95, 800)
        pm = QPixmap(b.size())
        b.render(pm)                      # 真画一遍，样式表写错这里就炸
        assert not pm.isNull()
    b.close()
    pump(win95, 300)


def test_预览窗格跟着调色板走(win95, workdir):
    """回归：预览窗格原来硬编码深色，套上灰底主题会留一块突兀的黑。"""
    b = Browser(workdir)
    b.resize(900, 600); b.show()
    pump(win95, 2000)
    pv = b._preview
    pm = QPixmap(pv.size()); pv.render(pm)
    img = pm.toImage()
    corner = img.pixelColor(3, 3)
    assert corner.lightness() > 100, f"预览窗格还是深色的：{corner.name()}"
    b.close(); pump(win95, 300)


def test_菜单开关能来回切(qapp, workdir):
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


# ------------------------------------------------------------------ 图标
def test_像素网格都是16x16(qapp):
    for name, grid in (("closed", theme.FOLDER_CLOSED),
                       ("open", theme.FOLDER_OPEN),
                       ("drive", theme.DRIVE),
                       ("floppy", theme.FLOPPY),
                       ("cdrom", theme.CDROM),
                       ("network", theme.NETWORK),
                       ("parent", theme.PARENT)):
        assert len(grid) == 16, f"{name} 行数不是 16"
        bad = [i for i, row in enumerate(grid) if len(row) != 16]
        assert not bad, f"{name} 第 {bad} 行宽度不是 16"
        unknown = {ch for row in grid for ch in row} - set(theme._ICON_COLORS) - {"."}
        assert not unknown, f"{name} 里有没定义的颜色字符：{unknown}"


def test_文件夹图标是黄的(qapp):
    pm = theme.folder_pixmap(16, False)
    img = pm.toImage()
    yellow = sum(1 for y in range(16) for x in range(16)
                 if img.pixelColor(x, y).name() == theme.ICON_FACE)
    assert yellow > 60, f"黄色像素只有 {yellow} 个，图标八成画错了"
    assert img.pixelColor(0, 0).alpha() == 0, "四角必须透明"


def test_打开与闭合的文件夹不一样(qapp):
    a = theme.folder_pixmap(16, False).toImage()
    b = theme.folder_pixmap(16, True).toImage()
    assert a != b, "展开状态得看得出区别，否则这个图标白做了"


def test_图标放大不糊(qapp):
    """像素画只能最近邻放大，平滑一次就不是 Win95 了。"""
    pm = theme.folder_pixmap(32, False)
    assert pm.size().width() == 32
    colors = {pm.toImage().pixelColor(x, y).name()
              for x in range(32) for y in range(32)
              if pm.toImage().pixelColor(x, y).alpha() > 0}
    allowed = set(theme._ICON_COLORS.values())
    assert colors <= allowed, f"放大后冒出了中间色，说明被平滑了：{colors - allowed}"


def test_目录树用上了win95图标(win95, workdir):
    from PySide6.QtWidgets import QFileIconProvider
    b = Browser(workdir)
    b.show(); pump(win95, 1500)
    b._toggle_win95(True)
    assert isinstance(b._fs.iconProvider(), theme.Win95IconProvider)
    b._toggle_win95(False)
    assert not isinstance(b._fs.iconProvider(), theme.Win95IconProvider)
    b.close(); pump(win95, 300)


def test_图标提供器有缓存(qapp):
    """icon(QFileInfo) 每一行都会调一次，不缓存就是每帧重画几十个图标。"""
    prov = theme.Win95IconProvider()
    a = prov._icon("folder")
    b = prov._icon("folder")
    assert a is b


def test_界面字体关掉抗锯齿(win95):
    """Win95 的界面字体是位图字体，一个像素都不糊。开着抗锯齿字发虚，
    整个界面立刻"现代"了 —— 这是最影响年代感的一处。"""
    from PySide6.QtGui import QFont
    assert theme.ui_font().styleStrategy() == QFont.NoAntialias
    assert win95.font().styleStrategy() == QFont.NoAntialias


def test_驱动器按类型给不同图标(qapp):
    from PySide6.QtWidgets import QFileIconProvider
    prov = theme.Win95IconProvider()
    drive = prov.icon(QFileIconProvider.Drive).pixmap(16, 16).toImage()
    net = prov.icon(QFileIconProvider.Network).pixmap(16, 16).toImage()
    folder = prov.icon(QFileIconProvider.Folder).pixmap(16, 16).toImage()
    assert drive != net != folder, "三类图标不该长一样"
