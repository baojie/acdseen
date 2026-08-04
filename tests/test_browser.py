"""浏览器：模型、缩略图按需加载、文件操作、排序。"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QMessageBox

from acdseen import config, i18n
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


def image_index(browser, n: int):
    """第 n 张图片在视图里的 QModelIndex —— 有 ".." 行时行号要偏移 1。"""
    m = browser._model
    return m.index(m.index_of(m.paths()[n]), 0)


def select_image(browser, n: int) -> None:
    browser._view.setCurrentIndex(image_index(browser, n))


@pytest.fixture
def yes(monkeypatch):
    """把确认对话框按成"是"。"""
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))


def test_列出目录里的图(browser, workdir):
    assert browser._model.image_count() == len(list_images(workdir))


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


def test_点软链接目录不跳到真实路径(qapp, tmp_path, pics):
    """回归：set_directory 曾用 resolve()，点软链接目录会跟着跳到真实路径，
    树上的选中行当场从你点的那一行蹦到别处。"""
    import os
    real = tmp_path / "real" / "photos"
    real.mkdir(parents=True)
    (real / "a.png").write_bytes((pics / "IMG_001.png").read_bytes())
    link = tmp_path / "link_to_photos"
    os.symlink(real, link)

    b = Browser(tmp_path)
    b.resize(900, 600)
    b.show()
    pump(qapp, 1500)

    fs, tree = b._fs, b._tree
    root = fs.index(str(tmp_path))
    fs.fetchMore(root)
    pump(qapp, 1000)

    idx = fs.index(str(link))
    assert idx.isValid(), "夹具没建出软链接，测试本身失效"
    tree.setCurrentIndex(idx)          # 等价于用户点这一行
    pump(qapp, 1000)

    assert b._dir == link, "当前目录应停在软链接本身"
    assert fs.filePath(tree.currentIndex()) == str(link), "树上不该跳到 real/photos"
    assert [p.name for p in b._model.paths()] == ["a.png"], "内容仍要正常列出"
    b.close()
    pump(qapp, 300)


def test_同步树选中不递归回调(qapp, browser, tmp_path):
    """set_directory 里的 setCurrentIndex 不该再触发 _on_tree_changed —
    currentChanged 连在 selectionModel 上，拦 QTreeView 的信号拦不住。"""
    calls = []
    orig = browser.set_directory
    browser.set_directory = lambda d: (calls.append(d), orig(d))[1]
    idx = browser._fs.index(str(tmp_path))
    if idx.isValid():
        browser._tree.setCurrentIndex(idx)
        pump(qapp, 500)
        assert len(calls) == 1, f"set_directory 被重入了：{calls}"
    browser.set_directory = orig


def test_幻灯演示从指定的那张开始(qapp, browser):
    browser._start_slideshow(2)
    pump(qapp, 500)
    v = browser._viewer
    assert v is not None, "应已切到看图页"
    assert v.current == browser._model.paths()[2], "该从第 3 张开始，不是第 1 张"
    assert v._slideshow.isActive(), "幻灯片没跑起来"
    browser._on_exit_view(None)
    pump(qapp, 300)


def test_幻灯演示起始张号越界会夹住(qapp, browser):
    n = browser._model.image_count()
    browser._start_slideshow(n + 99)
    pump(qapp, 500)
    assert browser._viewer.current == browser._model.paths()[n - 1]
    browser._on_exit_view(None)
    pump(qapp, 300)


def test_菜单栏幻灯片仍从第一张开始(qapp, browser):
    """triggered 会塞个 checked 布尔进来，直接连 _start_slideshow 会被当成张号。"""
    act = next(a for a in browser.actions() if a.text() == "从第一张开始幻灯片")
    act.trigger()
    pump(qapp, 500)
    assert browser._viewer.current == browser._model.paths()[0]
    browser._on_exit_view(None)
    pump(qapp, 300)


def test_右键菜单里有幻灯演示(qapp, browser):
    """只构造菜单不 exec —— exec 是模态的，测试里一弹就再也回不来。"""
    rect = browser._view.visualRect(image_index(browser, 0))
    m = browser._build_file_menu(rect.center())
    acts = [a.text() for a in m.actions()]
    assert "幻灯演示" in acts
    assert acts.index("幻灯演示") == acts.index("查看\tEnter") + 1, "应紧跟在「查看」下面"
    assert m.actions()[acts.index("幻灯演示")].isEnabled()
    m.deleteLater()


def test_右键点空白处幻灯演示不可用(qapp, browser):
    from PySide6.QtCore import QPoint
    browser._view.clearSelection()
    browser._view.setCurrentIndex(browser._model.index(-1, 0))
    m = browser._build_file_menu(QPoint(5, 100000))   # 列表下方的空白
    acts = [a.text() for a in m.actions()]
    assert not m.actions()[acts.index("幻灯演示")].isEnabled()
    m.deleteLater()


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
    select_image(browser, 0)

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
    select_image(browser, 0)

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
    select_image(browser, 0)
    browser._delete()
    pump(qapp, 300)
    assert not target.exists()
    assert target not in browser._model.paths()


def test_删除多选(qapp, browser, yes):
    sm = browser._view.selectionModel()
    targets = browser._model.paths()[:3]
    for r in range(3):
        sm.select(browser._model.index(r + browser._model._offset(), 0),
                  QItemSelectionModel.Select)
    browser._delete()
    pump(qapp, 300)
    assert not any(t.exists() for t in targets)


def test_复制粘贴到别的目录(qapp, browser, tmp_path):
    src = browser._model.paths()[0]
    select_image(browser, 0)
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
    assert b._model.image_count() == 0
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
    select_image(browser, 1)
    assert browser._preview._path == second
    pump(qapp, 8000, lambda: browser._preview._img is not None)
    select_image(browser, 0)
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


# ------------------------------------------------------------------ 视图模式
def test_默认是缩略图模式(browser):
    from PySide6.QtWidgets import QListView
    from acdseen.thumbmodel import ThumbDelegate
    assert browser._view_mode == config.VIEW_THUMBS
    assert browser._view is browser._icon_view
    assert browser._view.viewMode() == QListView.IconMode
    assert isinstance(browser._view.itemDelegate(), ThumbDelegate)


def test_切到列表模式(qapp, browser):
    from PySide6.QtWidgets import QTreeView
    browser._toggle_view_mode()
    pump(qapp, 500)
    assert browser._view_mode == config.VIEW_LIST
    assert isinstance(browser._view, QTreeView)
    assert browser._view is browser._list_view
    assert browser._model.thumb_size() == config.LIST_THUMB_SIZE
    browser._view.repaint()          # 列表模式必须画得出来


def test_切视图不丢选中项(qapp, browser):
    select_image(browser, 2)
    keep = browser._current_path()
    browser._toggle_view_mode()
    pump(qapp, 500)
    assert browser._current_path() == keep, "set_thumb_size 会重置模型，选中项要找回来"
    browser._toggle_view_mode()
    pump(qapp, 500)
    assert browser._current_path() == keep


def test_列表模式不覆盖缩略图边长(qapp, browser):
    """回归：列表模式把模型尺寸压到 40，那个值不能被当成用户选的缩略图大小存起来。"""
    browser._thumb_edge = 160
    browser._set_view_mode(config.VIEW_THUMBS)
    browser._model.set_thumb_size(160)
    browser._toggle_view_mode()      # → 列表
    pump(qapp, 300)
    assert browser._model.thumb_size() == config.LIST_THUMB_SIZE
    assert browser._thumb_edge == 160, "用户选的缩略图边长被列表模式吃掉了"
    browser._toggle_view_mode()      # → 缩略图
    pump(qapp, 300)
    assert browser._model.thumb_size() == 160, "切回来要恢复用户选的边长"


def test_列表模式下调缩略图大小会切回网格(qapp, browser):
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._step_thumb(+1)
    assert browser._view_mode == config.VIEW_THUMBS


def test_列表各列都有内容(browser):
    from PySide6.QtCore import Qt
    from acdseen.thumbmodel import (COL_DIMS, COL_MTIME, COL_NAME, COL_SIZE,
                                    COL_TYPE, COLUMNS)
    row = browser._model.index_of(
        next(p for p in browser._model.paths() if p.name != "broken.jpg"))
    cell = lambda c: browser._model.data(browser._model.index(row, c), Qt.DisplayRole)
    assert browser._model.columnCount() == len(COLUMNS)
    assert cell(COL_NAME)
    assert "×" in cell(COL_DIMS)
    assert cell(COL_SIZE)
    assert cell(COL_TYPE)
    assert cell(COL_MTIME)


def test_表头有标题(browser):
    from PySide6.QtCore import Qt
    from acdseen.thumbmodel import COLUMNS
    titles = [browser._model.headerData(i, Qt.Horizontal)
              for i in range(browser._model.columnCount())]
    # COLUMNS 第一列是 i18n 的 id，标题是翻译后的文本
    assert titles == [i18n.tr(t) for t, _k, _w in COLUMNS]
    hdr = browser._list_view.header()
    assert hdr.sectionsClickable(), "表头必须能点"


def test_视图模式持久化(qapp, workdir):
    b = Browser(workdir)
    b.show(); pump(qapp, 1500)
    b._set_view_mode(config.VIEW_LIST)
    b.close(); pump(qapp, 300)

    b2 = Browser(workdir)
    b2.show(); pump(qapp, 1500)
    assert b2._view_mode == config.VIEW_LIST, "视图模式没存进 QSettings"
    b2.close(); pump(qapp, 300)


# ------------------------------------------------------------------ 排序
def test_排序菜单覆盖全部排序键(browser):
    assert {k for _, k in browser._sort_acts} == set(config.SORT_NAMES)


def test_切排序会重排列表(qapp, browser):
    browser._set_sort(config.SORT_SIZE)
    pump(qapp, 500)
    sizes = [p.stat().st_size for p in browser._model.paths()]
    assert sizes == sorted(sizes)
    browser._set_sort(config.SORT_NAME)
    pump(qapp, 500)
    names = [p.name for p in browser._model.paths()]
    assert names == [p.name for p in list_images(browser._dir, config.SORT_NAME)]


def test_随机排序刷新时不重洗(qapp, browser):
    """删一张图会触发 refresh()，那时整个网格不该重排。"""
    browser._set_sort(config.SORT_RANDOM)
    pump(qapp, 500)
    before = list(browser._model.paths())
    browser.refresh()
    pump(qapp, 500)
    assert browser._model.paths() == before, "seed 没稳住，refresh 把顺序洗掉了"


def test_再点随机会重新洗牌(qapp, browser):
    browser._set_sort(config.SORT_RANDOM)
    pump(qapp, 300)
    first, seed = list(browser._model.paths()), browser._sort_seed
    browser._set_sort(config.SORT_RANDOM)
    pump(qapp, 300)
    assert browser._sort_seed != seed, "再点一次「随机」应该换一副新牌"
    assert sorted(browser._model.paths()) == sorted(first), "一张都不能丢"


# ------------------------------------------------------------------ 表头排序
def test_点表头按该列排序(qapp, browser):
    from acdseen.thumbmodel import COL_SIZE
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._on_header_clicked(COL_SIZE)
    pump(qapp, 500)
    assert browser._sort_key == config.SORT_SIZE
    sizes = [p.stat().st_size for p in browser._model.paths()]
    assert sizes == sorted(sizes)


def test_再点同一列翻转正倒序(qapp, browser):
    from acdseen.thumbmodel import COL_SIZE
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._on_header_clicked(COL_SIZE)
    pump(qapp, 400)
    up = list(browser._model.paths())
    assert not browser._sort_reverse
    browser._on_header_clicked(COL_SIZE)
    pump(qapp, 400)
    assert browser._sort_reverse
    assert browser._model.paths() == list(reversed(up))


def test_点别的列回到正序(qapp, browser):
    from acdseen.thumbmodel import COL_NAME, COL_SIZE
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._on_header_clicked(COL_SIZE)
    browser._on_header_clicked(COL_SIZE)      # 变倒序
    pump(qapp, 400)
    assert browser._sort_reverse
    browser._on_header_clicked(COL_NAME)      # 换一列
    pump(qapp, 400)
    assert browser._sort_key == config.SORT_NAME
    assert not browser._sort_reverse, "换列时该回到正序"
    assert browser._sort_rev_act.isChecked() is False, "菜单的「倒序」也要跟上"


def test_表头箭头跟随菜单排序(qapp, browser):
    from PySide6.QtCore import Qt
    from acdseen.thumbmodel import COL_SIZE
    hdr = browser._list_view.header()
    browser._set_sort(config.SORT_SIZE)
    pump(qapp, 300)
    assert hdr.isSortIndicatorShown()
    assert hdr.sortIndicatorSection() == COL_SIZE
    assert hdr.sortIndicatorOrder() == Qt.AscendingOrder
    browser._sort_rev_act.setChecked(True)
    browser._toggle_sort_order()
    pump(qapp, 300)
    assert hdr.sortIndicatorOrder() == Qt.DescendingOrder


def test_随机排序时收起箭头(qapp, browser):
    """随机不对应任何一列，硬指一个会误导。"""
    hdr = browser._list_view.header()
    browser._set_sort(config.SORT_RANDOM)
    pump(qapp, 300)
    assert not hdr.isSortIndicatorShown()


def test_列表模式多选不重复计数(qapp, browser):
    """QTreeView 一行有 5 个 index，去重没做的话一个文件会被数 5 遍。"""
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._view.selectAll()
    pump(qapp, 300)
    n = browser._model.image_count()
    # 全选会把 ".." 那一行也选上，所以 index 数按 rowCount 算
    assert len(browser._view.selectedIndexes()) == browser._model.rowCount() * 5
    assert len(browser._selected_paths()) == n, "\"..\" 不是图片，不该进选择集"
    assert f"已选 {n}" in browser._status_left.text()


def test_两个视图共享选中项(qapp, browser):
    select_image(browser, 2)
    keep = browser._current_path()
    assert browser._icon_view.selectionModel() is browser._list_view.selectionModel()
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    assert browser._current_path() == keep


# ------------------------------------------------------------------ 上级目录行
def test_列表第一行是上级目录(browser):
    m = browser._model
    idx = m.index(0, 0)
    assert m.is_parent_row(idx)
    assert m.data(idx, Qt.DisplayRole) == ".."
    assert m.parent_dir() == browser._dir.parent
    assert m.rowCount() == m.image_count() + 1


def test_上级目录行不是图片(browser):
    """它不该混进选择集、预览和文件操作 —— 那些地方全靠 path_at 返回 None 挡住。"""
    m = browser._model
    idx = m.index(0, 0)
    assert m.path_at(idx) is None
    assert m.image_index(idx) == -1
    browser._view.setCurrentIndex(idx)
    assert browser._current_path() is None
    assert browser._selected_paths() == [], "\"..\" 不该被当成选中的文件"


def test_双击上级目录行回上级(qapp, browser, workdir):
    parent = workdir.parent
    browser._open_index(browser._model.index(0, 0))
    pump(qapp, 800)
    assert browser._dir == parent


def test_根目录没有上级目录行(qapp):
    from pathlib import Path
    b = Browser(Path("/"))
    b.show(); pump(qapp, 1200)
    assert b._model.parent_dir() is None
    assert not b._model.is_parent_row(b._model.index(0, 0))
    b.close(); pump(qapp, 300)


def test_切目录后选中第一张图而不是上级行(qapp, browser):
    m = browser._model
    assert m.first_image_row() == 1
    assert not m.is_parent_row(browser._view.currentIndex())
    assert browser._current_path() == m.paths()[0]


def test_状态栏不把上级行算成图片(browser):
    n = len(browser._model.paths())
    assert f"{n} 张图片" in browser._status_left.text()


def test_上级目录行的右键菜单只有回上级(browser):
    m = browser._build_file_menu(browser._view.visualRect(
        browser._model.index(0, 0)).center())
    acts = [a.text() for a in m.actions()]
    assert acts == ["回到上级目录\tBackspace"]
    m.deleteLater()


# ------------------------------------------------------------------ 路径栏
def test_路径栏显示当前目录(browser, workdir):
    assert browser._path_bar.currentText() == str(workdir)


def test_路径栏下拉列出各级祖先(browser, workdir):
    items = [browser._path_bar.itemText(i)
             for i in range(browser._path_bar.count())]
    assert items[0] == str(workdir)
    assert items[-1] == "/"
    assert str(workdir.parent) in items


def test_路径栏输入路径可切目录(qapp, browser, workdir):
    target = workdir.parent
    browser._path_bar.setEditText(str(target))
    browser._on_path_entered()
    pump(qapp, 800)
    assert browser._dir == target


def test_路径栏切目录不会递归(qapp, browser, workdir):
    """回归：往 QComboBox 里塞条目会触发 activated，不挡信号就会
    从 set_directory 递归回 set_directory。"""
    calls = []
    orig = browser.set_directory
    browser.set_directory = lambda d: (calls.append(d), orig(d))[1]
    browser._on_path_picked(1)          # 选上级
    pump(qapp, 800)
    assert len(calls) == 1, f"set_directory 被重入了：{calls}"
    browser.set_directory = orig
