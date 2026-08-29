# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

A remake of ACDSee 1.2x (1996): one browser, one viewer. See `README.md`.

The scope is deliberately narrow, and the narrowness is the product. Before
adding anything, check it against `README.md`'s "Which version this remakes"
table. Tagging, EXIF panels, editing, batch processing and plugins are all
**out of scope on purpose** — they arrived in ACDSee 3.0 and are the reason a
simple image viewer is hard to find today. `ref/win95-gaps.md` records what is
deliberately not being built and why (priority C in particular).

## Commands

```bash
./setup.sh                              # create .venv, install dependencies
./run.sh [directory | image]            # run (equivalent to python -m acdseen)
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest              # tests, offscreen, no display needed
.venv/bin/python -m pytest tests/test_loader.py -k thumbnail   # a single test
```

Tests run under `QT_QPA_PLATFORM=offscreen`. `tests/conftest.py` redirects the
thumbnail cache and `QSettings` to temporary directories at session scope — keep
it that way, or a test run will overwrite the user's real configuration.

## Architecture

`browser.py` and `viewer.py` are hosts; most of their behavior lives in mixins:

- Browser: `viewpanes` (thumbnail grid + detail list), `menus`, `fileops`,
  `viewhost` (browse ↔ view page switching), plus `thumbmodel`
  (the shared multi-column model) and `preview` (the preview pane)
- Viewer: `slideshow`, `render` (paintEvent and the OSD overlay)

These are mixins rather than standalone classes because the coupling to the host
is real — they read the selection, refresh the list, write to the status bar.
**Every mixin's module docstring lists the host attributes and methods it
depends on. Update that list when you change what a mixin touches.**

`loader.py` is the decode layer and the reason the app feels instant: two-stage
decode (scaled preview first, full resolution swapped in behind it), pre-read of
neighbors into an LRU, and a separate thread pool plus disk cache for
thumbnails. Stale work is discarded by generation counter (directory changes)
and by token (image loads). Do not make it "simpler" without reading
`README.md`'s "How it works" first.

`config.py` holds the feel parameters — zoom steps, cache sizes, pre-read count,
thumbnail sizes. Tuning behavior means editing values there, not scattering
constants through the widgets.

`theme.py` is the Windows 95 look: palette, stylesheet, and a `QProxyStyle` for
the parts stylesheets cannot draw (tree `+/-` boxes, dotted connectors,
scrollbar arrows). The retro appearance is intentional — never "modernize" it.
The full-screen viewer is exempt: the original was plain black.

### Threading rule

Qt objects, and anything that touches the Qt bindings, stay off worker threads.
Pillow's fallback path in particular must not go through `PIL.ImageQt` — build
the `QImage` from raw bytes instead, and keep the PIL fallback serialized behind
its lock. Three tests in `tests/test_loader.py` exist solely to hold this line;
they map to real crashes (including process-level fatal errors) and must not be
deleted.

## Conventions

- **Comments and docstrings are in English.** They explain *why* a trade-off was
  made, not what the line does. Match the surrounding density. Any non-English
  text left in the source is data, never prose: the `lang_*.py` translation
  tables, the language names in `i18n.LANG_NAMES`, and the expected UI strings
  that `tests/test_language.py` asserts against.
- **User-visible strings go through `tr(id)`** (`i18n.py`). Every string has its
  own id (`action.open`, `status.images`); no language is embedded in the code.
  Translations live in `lang_<code>.py` — currently zh / en / ja / es / fr.
  Lookup falls back to English and then to the id itself, which makes
  `lang_en.py` the authoritative list of ids: add there first, then translate.
- **Documentation is English-first**: `README.md`, `CHANGELOG.md` and
  `ref/win95-gaps.md` are the defaults; the `*.zh-CN.md` files are translations
  of them. Update both, and keep each file's internal links pointing at files
  in its own language.
- **Commit messages are in English.** Explain why the change was made, not just
  what changed; wrap the body at roughly 78 columns.
- **Daily logs in `logs/daily/<YYYY-MM>/<YYYY-MM-DD>.md` are in English too**,
  headings included — they are project documentation, and the rule above
  applies to them like to everything else committed here. A day runs 07:00 to
  07:00, so a session that runs past midnight stays with the day it began.
- Work directly on the current branch — no feature branches for new work.
- Record changes in `CHANGELOG.md` (and `CHANGELOG.zh-CN.md`) under
  `[Unreleased]`, grouped by day, newest first.
