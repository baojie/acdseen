"""界面语言：id → 显示文本的多语言查表。

每个用户可见的字符串都有一个独立 id（如 "action.open"、"status.images"），
代码里 tr(id) 按当前语言查表。任何语言都不直接携带文本，文本全在
lang_<code>.py 的翻译表里 —— 加一种新语言只是新增一个 lang_ 模块。

回退规则：当前语言表查不到 → 英文表 → 最后才是 id 本身。所以英文表
（lang_en.py）是所有 id 的权威清单，必须最全。

语言状态是模块级的（不做成对象）：界面到处都在调 tr()，传引用只会更绕。
测试里用 set_language 复位，和 QSettings 一样是每个用例的隔离点。
"""

from __future__ import annotations

import importlib

LANG_ZH = "zh"
LANG_EN = "en"
LANG_JA = "ja"
LANG_ES = "es"
LANG_FR = "fr"

# 语言代码 → 用目标语言自称的显示名（语言名不翻译，否则自己读不懂自己）
LANG_NAMES = {
    LANG_ZH: "简体中文",
    LANG_EN: "English",
    LANG_JA: "日本語",
    LANG_ES: "Español",
    LANG_FR: "Français",
}

_current = LANG_ZH

_TABLES: dict[str, dict] = {}


def current() -> str:
    return _current


def system_default() -> str:
    """跟随系统 locale：中文系统用汉语，其余用英语。"""
    import locale
    try:
        code, _ = locale.getlocale()
    except Exception:
        return LANG_ZH
    if code and code.lower().startswith("zh"):
        return LANG_ZH
    return LANG_EN


def set_language(code: str) -> None:
    """切换语言。只认 LANG_NAMES 里的值，别的忽略。"""
    global _current
    if code in LANG_NAMES:
        _current = code


def _table(code: str) -> dict:
    """取某语言的翻译表（惰性 import，第一次用到才加载）。"""
    if code not in _TABLES:
        mod = importlib.import_module(f".lang_{code}", __package__)
        _TABLES[code] = mod.TRANSLATIONS
    return _TABLES[code]


def tr(text_id: str, *args, **kwargs) -> str:
    """按当前语言查 id 得显示文本，再套占位符格式化。

    查不到 id 时依次回退英文表、id 本身 —— 宁可露出英文或 id 也不炸。
    带 {} / {name} 占位符的翻译值，由 str.format 统一填充；格式化失败
    就回退到未格式化的原文，宁可露出占位符也不炸。
    """
    out = _table(_current).get(text_id) or _table(LANG_EN).get(text_id, text_id)
    if args or kwargs:
        try:
            return out.format(*args, **kwargs)
        except (IndexError, KeyError, ValueError):
            return out
    return out
