"""界面语言的翻译机制与切换。"""

import pytest

from acdseen import config, i18n
from acdseen.browser import Browser
from conftest import pump


def test_tr_中文查表(qapp):
    i18n.set_language(i18n.LANG_ZH)
    assert i18n.tr("action.open") == "打开"
    assert i18n.tr("status.images", 5) == "5 张图片"


def test_tr_英文查表(qapp):
    i18n.set_language(i18n.LANG_EN)
    assert i18n.tr("action.open") == "Open"
    assert i18n.tr("status.images", 5) == "5 images"
    assert i18n.tr("slideshow.seconds", 3.0) == "3 s"
    assert i18n.tr("err.decode", "x.jpg") == "Cannot decode x.jpg"
    i18n.set_language(i18n.LANG_ZH)


def test_tr_各语言都能查到(qapp):
    """日语 / 西班牙语 / 法语同样走 id 查表。"""
    for code, expected in [("ja", "開く"), ("es", "Abrir"), ("fr", "Ouvrir")]:
        i18n.set_language(code)
        assert i18n.tr("action.open") == expected
    i18n.set_language(i18n.LANG_ZH)


def test_tr_查不到就回退(qapp):
    i18n.set_language(i18n.LANG_JA)
    # 英文表里也没有的 id → 回退到 id 本身，绝不炸
    assert i18n.tr("no.such.id") == "no.such.id"
    i18n.set_language(i18n.LANG_ZH)


def test_tr_日语重排占位符(qapp):
    """status.transferred 在日语里词序不同，靠命名占位符重排。"""
    i18n.set_language(i18n.LANG_JA)
    assert i18n.tr("status.transferred",
                   verb="移動", count=3, dest="/tmp") == "3 個のファイルを /tmp に移動しました"
    i18n.set_language(i18n.LANG_ZH)


def test_系统默认语言是合法值():
    assert i18n.system_default() in i18n.LANG_NAMES


def test_非法语言被忽略():
    before = i18n.current()
    i18n.set_language("xx")
    assert i18n.current() == before


@pytest.fixture
def browser(qapp, workdir):
    b = Browser(workdir)
    b.resize(1100, 720)
    b.show()
    pump(qapp, 2000)
    yield b
    b.close()
    pump(qapp, 300)


def test_切换语言立即刷新(qapp, browser):
    """菜单和状态栏切完立刻换语言，不用重启。"""
    assert i18n.current() == i18n.LANG_ZH
    browser._set_language(i18n.LANG_EN)
    texts = {a.text() for a in browser.actions()}
    assert "Open" in texts
    assert "Start slideshow from first" in texts
    assert "Shortcuts" in texts
    assert browser._status_left.text().endswith("images")

    browser._set_language(i18n.LANG_ZH)
    texts = {a.text() for a in browser.actions()}
    assert "打开" in texts
    assert "从第一张开始幻灯片" in texts


def test_语言选择持久化(qapp, browser):
    browser._set_language(i18n.LANG_EN)
    assert browser._settings.value("language") == i18n.LANG_EN
