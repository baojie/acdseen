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
    browser._toggle_tree()
    assert browser._splitter.sizes()[0] == 0
    browser._toggle_tree()
    assert browser._splitter.sizes()[0] > 0


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


# ------------------------------------------------------------------ 与看图器联动
def test_打开看图器时暂停缩略图池(qapp, browser):
    assert not browser._loader._paused
    v = browser._open_viewer(0)
    assert browser._loader._paused, "看图时缩略图仍在抢 CPU"
    v.close()
    pump(qapp, 500)
    assert not browser._loader._paused, "看图器关了没恢复缩略图加载"


def test_看图器删除文件同步到列表(qapp, browser, yes):
    v = browser._open_viewer(0)
    pump(qapp, 4000, lambda: v._image is not None)
    doomed = v.current
    v.delete_current()
    pump(qapp, 500)
    assert doomed not in browser._model.paths()
    v.close()


def test_关闭看图器后选中回到当前图(qapp, browser):
    v = browser._open_viewer(2)
    pump(qapp, 4000, lambda: v._image is not None)
    expected = v.current
    v.close()
    pump(qapp, 500)
    assert browser._model.path_at(browser._view.currentIndex()) == expected


def test_空目录不崩溃(qapp, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    b = Browser(empty)
    b.show()
    pump(qapp, 500)
    assert b._model.rowCount() == 0
    b._update_status()
    b.close()
