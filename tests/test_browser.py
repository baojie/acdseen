"""浏览器：模型、缩略图按需加载、文件操作、排序。"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QMessageBox

from acdseen import config
from acdseen.browser import Browser
from acdseen.util import list_images
from conftest import pump


@pytest.fixture
def browser(qapp, workdir):
    b = Browser(workdir)
    b.resize(1100, 720)
    b.show()
    pump(qapp, 4000)
    yield b
    b.close()
    pump(qapp, 300)


@pytest.fixture
def yes(monkeypatch):
    """把确认对话框按成"是"。"""
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))


def test_列出目录里的图(browser, workdir):
    assert browser._model.rowCount() == len(list_images(workdir))


def test_可见项拿到缩略图(qapp, browser):
    """只要求可见项 —— 不可见的不该白解码。"""
    assert pump(qapp, 15000, lambda: len(browser._model._thumbs) > 0)
    thumbs = [t for t in browser._model._thumbs.values() if t is not None]
    assert thumbs


def test_损坏文件显示破图标而非崩溃(qapp, browser, workdir):
    broken = workdir / "broken.jpg"
    browser._model._requested.add(broken)
    browser._loader.request(broken, browser._model.thumb_size())
    assert pump(qapp, 8000, lambda: broken in browser._model._thumbs)
    assert browser._model._thumbs[broken] is not None   # 是破图标，不是 None


def test_切换排序改变顺序(browser):
    by_name = [p.name for p in browser._model.paths()]
    browser._set_sort(config.SORT_SIZE)
    by_size = [p.name for p in browser._model.paths()]
    assert sorted(by_name) == sorted(by_size)
    assert by_name != by_size


def test_倒序(browser):
    forward = [p.name for p in browser._model.paths()]
    browser._sort_rev_act.setChecked(True)
    browser._toggle_sort_order()
    assert [p.name for p in browser._model.paths()] == forward[::-1]


def test_缩略图尺寸步进(browser):
    start = browser._model.thumb_size()
    browser._step_thumb(+1)
    assert browser._model.thumb_size() > start
    browser._step_thumb(-1)
    assert browser._model.thumb_size() == start


def test_缩略图尺寸不越界(browser):
    for _ in range(20):
        browser._step_thumb(+1)
    assert browser._model.thumb_size() == config.THUMB_SIZES[-1]
    for _ in range(20):
        browser._step_thumb(-1)
    assert browser._model.thumb_size() == config.THUMB_SIZES[0]


def test_切目录树可见性(browser):
    """F9 只收目录树，预览窗格留在原地。"""
    assert browser._left_splitter.sizes()[0] > 0
    browser._toggle_tree()
    assert browser._left_splitter.sizes()[0] == 0
    browser._toggle_tree()
    assert browser._left_splitter.sizes()[0] > 0


def test_预览窗格可见性开关(browser):
    """模拟菜单点击：Qt 先切 checked，再发 triggered 调 _toggle_preview。"""
    assert browser._preview.isVisible()
    browser._preview_act.setChecked(False)
    browser._toggle_preview()
    assert not browser._preview.isVisible()
    browser._preview_act.setChecked(True)
    browser._toggle_preview()
    assert browser._preview.isVisible()


# ------------------------------------------------------------------ 文件操作
def test_重命名(qapp, browser, workdir):
    from PySide6.QtWidgets import QInputDialog
    target = browser._model.paths()[0]
    browser._view.setCurrentIndex(browser._model.index(0, 0))

    import acdseen.browser as B
    orig = QInputDialog.getText
    QInputDialog.getText = staticmethod(lambda *a, **k: ("renamed" + target.suffix, True))
    try:
        browser._rename()
    finally:
        QInputDialog.getText = orig

    assert not target.exists()
    assert (workdir / ("renamed" + target.suffix)).exists()


def test_重命名到已存在的名字会拒绝(qapp, browser, workdir, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    paths = browser._model.paths()
    first, second = paths[0], paths[1]
    browser._view.setCurrentIndex(browser._model.index(0, 0))

    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(a)))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (second.name, True)))
    browser._rename()

    assert warned, "覆盖同名文件必须被拦住"
    assert first.exists() and second.exists()


def test_删除选中(qapp, browser, yes):
    target = browser._model.paths()[0]
    browser._view.setCurrentIndex(browser._model.index(0, 0))
    browser._delete()
    pump(qapp, 300)
    assert not target.exists()
    assert target not in browser._model.paths()


def test_删除多选(qapp, browser, yes):
    sm = browser._view.selectionModel()
    targets = browser._model.paths()[:3]
    for r in range(3):
        sm.select(browser._model.index(r, 0), QItemSelectionModel.Select)
    browser._delete()
    pump(qapp, 300)
    assert not any(t.exists() for t in targets)


def test_复制粘贴到别的目录(qapp, browser, tmp_path):
    src = browser._model.paths()[0]
    browser._view.setCurrentIndex(browser._model.index(0, 0))
    browser._copy()
    assert browser._clipboard[0] == "copy"

    dest = tmp_path / "dest"
    dest.mkdir()
    browser._do_transfer([src], dest, move=False)
    assert (dest / src.name).exists()
    assert src.exists(), "复制不该动原文件"


def test_剪切是移动(qapp, browser, tmp_path):
    src = browser._model.paths()[0]
    dest = tmp_path / "moved"
    dest.mkdir()
    browser._do_transfer([src], dest, move=True)
    assert (dest / src.name).exists()
    assert not src.exists()


def test_同名冲突自动改名不覆盖(qapp, browser, tmp_path):
    src = browser._model.paths()[0]
    dest = tmp_path / "clash"
    dest.mkdir()
    (dest / src.name).write_bytes(b"existing content")

    browser._do_transfer([src], dest, move=False)
    assert (dest / src.name).read_bytes() == b"existing content", "原文件被覆盖了"
    assert (dest / f"{src.stem} (2){src.suffix}").exists()


def test_粘贴到当前目录不自我覆盖(qapp, browser, workdir):
    src = browser._model.paths()[0]
    before = src.read_bytes()
    browser._clipboard = ("copy", [src])
    browser._paste()
    pump(qapp, 300)
    assert src.read_bytes() == before


# ------------------------------------------------------------------ 看图模式
def test_看图不开新窗口(qapp, browser):
    """核心要求：看图是同一个窗口里换一页，不是弹窗。"""
    from PySide6.QtWidgets import QApplication

    def visible_windows():
        return [w for w in QApplication.topLevelWidgets()
                if w.isWindow() and w.isVisible()]

    before = len(visible_windows())
    v = browser._open_viewer(0)
    pump(qapp, 1000)
    assert len(visible_windows()) == before, "弹出了新窗口"
    assert browser._stack.currentWidget() is v
    assert not v.isWindow(), "看图页必须是子控件，不是独立窗口"


def test_进出看图模式切换页面(qapp, browser):
    assert not browser.is_viewing()
    v = browser._open_viewer(0)
    assert browser.is_viewing()
    assert browser._stack.currentWidget() is v

    browser._on_exit_view(None)
    pump(qapp, 500)
    assert not browser.is_viewing()
    assert browser._stack.currentWidget() is browser._splitter


def test_看图时隐藏状态栏(qapp, browser):
    assert browser._status.isVisible()
    browser._open_viewer(0)
    pump(qapp, 300)
    assert not browser._status.isVisible(), "看图时信息走 OSD，状态栏是多余的"
    browser._on_exit_view(None)
    pump(qapp, 300)
    assert browser._status.isVisible()


def test_看图时禁用浏览器快捷键(qapp, browser):
    """Del / Enter / F5 等 WindowShortcut 会抢在 Viewer.keyPressEvent 之前触发。"""
    assert all(a.isEnabled() for a in browser._browse_actions)
    browser._open_viewer(0)
    assert all(not a.isEnabled() for a in browser._browse_actions)
    browser._on_exit_view(None)
    pump(qapp, 300)
    assert all(a.isEnabled() for a in browser._browse_actions)


def test_看图时空格翻页不被抢走(qapp, browser):
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    v = browser._open_viewer(0)
    pump(qapp, 4000, lambda: v._image is not None)
    QApplication.sendEvent(v, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Space, Qt.NoModifier))
    pump(qapp, 1500)
    assert v._index == 1, "空格被浏览器快捷键吃掉了"


def test_全屏看图时收起菜单栏(qapp, browser):
    v = browser._open_viewer(0)
    pump(qapp, 500)
    v.toggle_fullscreen()
    pump(qapp, 800)
    assert browser.isFullScreen()
    assert not browser.menuBar().isVisible(), "全屏时屏幕上只该剩那张图"

    v.toggle_fullscreen()
    pump(qapp, 800)
    assert browser.menuBar().isVisible()


def test_退出看图时一并退出全屏(qapp, browser):
    v = browser._open_viewer(0)
    pump(qapp, 500)
    v.toggle_fullscreen()
    pump(qapp, 800)
    browser._on_exit_view(None)
    pump(qapp, 800)
    assert not browser.isFullScreen(), "回到浏览页却还全屏着，菜单栏都没了"
    assert browser.menuBar().isVisible()


def test_打开看图器时暂停缩略图池(qapp, browser):
    assert not browser._loader._paused
    browser._open_viewer(0)
    assert browser._loader._paused, "看图时缩略图仍在抢 CPU"
    browser._on_exit_view(None)
    pump(qapp, 500)
    assert not browser._loader._paused, "退出看图后没恢复缩略图加载"


def test_看图器删除文件同步到列表(qapp, browser, yes):
    v = browser._open_viewer(0)
    pump(qapp, 4000, lambda: v._image is not None)
    doomed = v.current
    v.delete_current()
    pump(qapp, 500)
    assert doomed not in browser._model.paths()
    browser._on_exit_view(None)


def test_退出看图后选中回到当前图(qapp, browser):
    v = browser._open_viewer(2)
    pump(qapp, 4000, lambda: v._image is not None)
    expected = v.current
    v.exit_view.emit(v.current)      # 等价于按 Esc
    pump(qapp, 500)
    assert browser._model.path_at(browser._view.currentIndex()) == expected


def test_重复打开看图器不泄漏页面(qapp, browser):
    n = browser._stack.count()
    for i in range(3):
        browser._open_viewer(i)
        pump(qapp, 300)
    browser._on_exit_view(None)
    pump(qapp, 500)
    assert browser._stack.count() == n, "旧的看图页没被拆掉"


def test_空目录不崩溃(qapp, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    b = Browser(empty)
    b.show()
    pump(qapp, 500)
    assert b._model.rowCount() == 0
    b._update_status()
    b.close()


# ------------------------------------------------------------------ 预览窗格
def test_选中项出现在预览窗格(qapp, browser):
    # 注意别拿 paths()[0]：自然排序下 broken.jpg 排在 IMG_xxx 前面，
    # 那是夹具故意放的损坏文件，永远解不出图。这里要一张真能解的。
    target = next(p for p in browser._model.paths() if p.name != "broken.jpg")
    browser._view.setCurrentIndex(browser._model.index(browser._model.index_of(target), 0))
    assert browser._preview._path == target, "选中项应进预览"
    assert pump(qapp, 8000, lambda: browser._preview._img is not None)
    assert not browser._preview._error


def test_切换选中项时预览跟着换(qapp, browser):
    first, second = browser._model.paths()[0], browser._model.paths()[1]
    browser._view.setCurrentIndex(browser._model.index(1, 0))
    assert browser._preview._path == second
    pump(qapp, 8000, lambda: browser._preview._img is not None)
    browser._view.setCurrentIndex(browser._model.index(0, 0))
    assert browser._preview._path == first


def test_损坏文件预览标记错误而非崩溃(qapp, browser, workdir):
    browser._preview.show_path(workdir / "broken.jpg")
    assert pump(qapp, 6000, lambda: browser._preview._error)
    browser._preview.repaint()          # 错误态也必须能画出来


def test_空目录预览清空(qapp, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    b = Browser(empty)
    b.show()
    pump(qapp, 500)
    assert b._preview._path is None
    assert b._preview.isVisible(), "预览窗格本身还在，只是显示占位提示"
    b.close()


def test_看图时预览暂停_退出后恢复(qapp, browser):
    browser._open_viewer(0)
    pump(qapp, 500)
    pv = browser._preview
    assert pv._paused, "看图时预览应处于暂停态"
    assert pv._img is None, "暂停应作废在飞解码"
    # 关键回归：切页会触发 resize，暂停态下不许被防抖定时器重新拉起来
    assert not pv._resize_timer.isActive()
    assert pump(qapp, 2000, lambda: pv._pool.activeThreadCount() == 0), \
        "看图时不该还有预览解码线程在跑"

    browser._on_exit_view(None)
    pump(qapp, 500)
    assert not pv._paused
    assert pv._path == browser._current_path(), "退出看图后预览应回到选中项"
    assert pump(qapp, 8000, lambda: pv._img is not None or pv._error), "退出后应恢复解码"
