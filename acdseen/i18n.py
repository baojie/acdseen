"""UI language: id → display text lookup across multiple languages.

Every user-visible string has a stable id (e.g. "action.open",
"status.images"); the code calls tr(id) and the current language is
resolved from a lookup table. No language carries its text inline —
all text lives in the lang_<code>.py tables, so adding a language is
just adding one more lang_ module.

Fallback: current-language table → English table → the id itself.
lang_en.py is therefore the authoritative index of every id and must
be the most complete.

The language state is module-level (not an object): the UI calls tr()
everywhere, so threading a reference around would only add noise.
Tests reset it with set_language, alongside the QSettings isolation.
"""

from __future__ import annotations

import importlib

LANG_ZH = "zh"
LANG_EN = "en"
LANG_JA = "ja"
LANG_ES = "es"
LANG_FR = "fr"

# Language code → display name in that language (language names are not
# translated, otherwise a language could not recognize itself).
LANG_NAMES = {
    LANG_ZH: "简体中文",
    LANG_EN: "English",
    LANG_JA: "日本語",
    LANG_ES: "Español",
    LANG_FR: "Français",
}

_current = LANG_EN

_TABLES: dict[str, dict] = {}


def current() -> str:
    return _current


def system_default() -> str:
    """The default UI language is English, regardless of the system locale."""
    return LANG_EN


def set_language(code: str) -> None:
    """Switch the language. Values outside LANG_NAMES are ignored."""
    global _current
    if code in LANG_NAMES:
        _current = code


def _table(code: str) -> dict:
    """Return the translation table for a language (lazy import on first use)."""
    if code not in _TABLES:
        mod = importlib.import_module(f".lang_{code}", __package__)
        _TABLES[code] = mod.TRANSLATIONS
    return _TABLES[code]


def tr(text_id: str, *args, **kwargs) -> str:
    """Look up the current language's text for an id, then format placeholders.

    Missing ids fall back to English, then to the id itself — better to show
    English or the raw id than to crash. Translation values with {} / {name}
    placeholders are filled with str.format; if formatting fails the
    unformatted value is returned instead of raising.
    """
    out = _table(_current).get(text_id) or _table(LANG_EN).get(text_id, text_id)
    if args or kwargs:
        try:
            return out.format(*args, **kwargs)
        except (IndexError, KeyError, ValueError):
            return out
    return out
