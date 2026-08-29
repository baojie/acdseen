# Changelog

*[简体中文](CHANGELOG.zh-CN.md)*

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

Recorded by day, newest first.

### 2026-08-30 — An icon of its own

#### Added

- **Application icon** (`appicon.py`): a framed photo with a magnifier over
  its lower-right corner, dotted out cell by cell on a character grid the same
  way `theme.py` draws the folder and drive icons — black outline, flat Win95
  fills, no gradients and no anti-aliasing
  - Two grids, not one: 32x32 for everything the dock and the switcher show,
    and a separate 16x16 cut whose magnifier is a 5x5 ring with the corners
    knocked off. Shrinking the 32x32 art to 16 turns the lens into mud
  - Larger sizes scale up by an integer factor with nearest-neighbor so the
    pixels stay square; only sizes that are not a multiple of the grid (48 is
    the common one) are resampled smoothly
  - `main.py` sets it as the window icon and calls `setDesktopFileName()`, so
    the desktop shell can tie a running window back to its launcher
- **`install-desktop.sh`**: writes the icon into `~/.local/share/icons`, an
  `acdseen.desktop` entry into `~/.local/share/applications`, and with
  `--dock` pins it to the GNOME dock. `--uninstall` reverses all three.
  Everything stays under `~/.local` — no root, nothing outside the home dir

### 2026-08-04 — Getting ready to publish

#### Added

- **Five interface languages** (`i18n.py` + `lang_<code>.py`): English,
  简体中文, 日本語, Español, Français, switchable under **View → Language**
  - Every user-visible string has its own id (`action.open`, `status.images`)
    and the code calls `tr(id)` — no language is embedded in the code, so
    adding a language means adding one `lang_` module and nothing else
  - Lookup falls back from the current language to English to the id itself,
    which makes `lang_en.py` the authoritative list of ids
  - Switching takes effect immediately, without a restart: the menu bar is
    rebuilt, and the status bar, window title, preview hint and viewer title
    are re-rendered. The choice persists via `QSettings`; the first run
    follows the system locale
  - Language names in the menu are written in their own language and never
    translated — otherwise a language can't recognize itself
  - `helptext.py` is gone: the F1 shortcut table is now part of the
    translation tables like every other string
- **MIT license** (`LICENSE`): without one, "all rights reserved" applies and
  nobody can legally fork the project
- **Packaging metadata**: `pyproject.toml` gains `readme` / `license` /
  `license-files` / `[project.urls]`, so `pip install .` gives you an `acdseen`
  command
  - build requirement raised to `setuptools>=77`: the PEP 639 string form of
    `license` needs 77+
- **Browser screenshot in the README** (`ref/screenshot-browser.png`)

#### Changed

- **README rewritten for a public audience**: added "Why this exists" (thirty
  years on, the best image viewer is still the old ACDSee, and all I want is to
  look at pictures); stated plainly that the retro look is deliberate rather than
  unfinished, with instructions for turning it off; added `git clone` /
  `pip install .` / a platform note (only "open in file manager" uses `xdg-open`)
- **Version history corrected**: ACDSee first shipped in 1994 for Windows 3.x and
  this project remakes 1.2x (1996). Dropped the section explaining that ACDSee
  was never a DOS program — that was trivia, not documentation

### 2026-08-03 — Windows 95 look, list mode, module split

#### Added

- **Windows 95 look** (`theme.py`, on by default, switchable under
  **View → Windows 95 look**): built to match ACDSee 2.x on Win95 — `#C0C0C0`
  grey, 2px chiseled borders (white top-left / dark grey bottom-right, inverted
  when sunken), `#000080` full-row navy selection with white text, raised header
  buttons, square-arrow scrollbars, a sunken segmented status bar
  - The tree's `+/-` boxes and dotted connector lines, and the scrollbar arrows,
    are painted by a `QProxyStyle` — stylesheets can't draw them
  - The preview pane now takes every color from the palette instead of
    hard-coded dark values, so the grey theme no longer leaves a black rectangle
  - The full-screen viewer is exempt: the original Viewer was plain black
  - The on/off state persists via `QSettings`
- **Path bar**: shows the current directory in the top right, accepts a typed
  path on Enter, and drops down the ancestor chain
- **`..` as the first row**: click it to go up, with a sideways yellow folder icon
  - The model distinguishes "navigation rows" from "image rows" explicitly:
    `_paths` holds only images, the two numbering schemes convert through
    `_offset()`, `path_at()` returns `None` for navigation rows, and selection /
    preview / file operations all rely on that one guard
- **Drive icons by type**: floppy / CD-ROM / network neighborhood each get their
  own 16×16 pixel grid (Linux has no drive letters, so this can only guess from
  mount point names — limited payoff)
- **List mode in the browser** (`F8` / `Ctrl+1` `Ctrl+2`): a `QTreeView` detail
  list with Name / Dimensions / Size / Type / Date modified columns
  - **Click-to-sort headers**: click once to sort by that column, again to
    reverse; switching columns starts ascending. Columns can be resized and
    reordered, and the sort indicator stays in sync with the Sort menu both ways
    (random sort matches no column, so the arrow is hidden)
  - The model became a multi-column `QAbstractTableModel` shared by both views
    along with a single selection model, so switching views preserves the
    thumbnail cache and the selection; the view mode persists via `QSettings`
- **More sort options**: beyond name / file size / type / date modified, now
  **total pixels**, **width**, **height** and **random**, each combinable with
  reverse order
  - Dimension sorts have to read each file's image header, cached by path +
    mtime, so scrolling and refreshing don't re-read
  - Random sort uses a fixed seed, so the refresh triggered by deleting an image
    doesn't reshuffle the whole grid; picking "random" again deals a new hand
- **Zoom mode "scale to display box"** (`Z`), now **the default**: single images
  and slideshows both fill the window, enlarging small images to touch the edges,
  aspect ratio preserved, no cropping
  - The existing "fit to window" (`*`) keeps the original ACDSee behavior of not
    enlarging small images
  - The zoom mode now carries across images: after zooming by hand, paging
    returns to the mode you chose rather than always falling back to fit
  - Enlargement up to 2× switched to smooth interpolation (previously always
    nearest-neighbor, which turned small images into mush); beyond 2× it stays
    nearest-neighbor, because at that point you are looking at pixels
- **"Slideshow" in the thumbnail context menu**: starts from the image you
  right-clicked, complementing `Ctrl+S` (which starts from the first)
- **Slideshow interval in arbitrary seconds**: `D` in the viewer, or "Slideshow
  interval…" in the context menu, opens a dialog spanning 0–3600 seconds
  - `0` seconds = as fast as possible: advance the moment the decode finishes,
    without waiting on the wall clock
  - `[` / `]` steps gained `0` and `0.5`
- **Slideshow shuffle**: `R` in the viewer, or "Shuffle" in the context menu;
  reshuffles automatically after each full pass. Turning it off restores the
  original order, and the current image never moves

#### Changed

- **Split every module over 500 lines by function**, behavior unchanged, not one
  test modified:
  - `browser.py` 829 → 292 lines, splitting out `thumbmodel.py` / `viewpanes.py` /
    `menus.py` / `fileops.py` / `viewhost.py` / `helptext.py`
  - `viewer.py` 593 → 413 lines, splitting out `slideshow.py` / `render.py`
  - Mixins rather than standalone classes: attribute paths stay the same, and the
    real coupling to the host doesn't have to masquerade as callbacks

#### Fixed

- **Antialiasing was on for the UI font**: Win95's UI font is a bitmap font,
  crisp to the pixel. With antialiasing the text goes soft and the whole
  interface immediately reads as "modern". Now set to `QFont.NoAntialias`
- **Concurrent preview-pane decodes could segfault**: `warmup()` only covered
  Pillow's lazy import of the plugin registry, not the part inside
  `PILImage.open()` that probes plugins one by one — a corrupt file walks the
  entire plugin list, and several worker threads probing at once is a guaranteed
  crash. The PIL fallback is a cold path for formats Qt doesn't recognize
  anyway, so the whole thing is now serialized behind a lock

### 2026-08-02 — Preview pane and embedded viewer

#### Added

- **Preview pane** (`preview.py`): shows the selected image large, at the bottom
  left of the browser
  - Recreates the Preview Pane of the original ACDSee 1.x (the Mac 1.5.1 build
    put it bottom-left by default)
  - Single-threaded decode with generation-based invalidation; the decode target
    follows the pane's size, and resizes debounce through a single-shot QTimer
  - Stays in sync with the selection, directory changes and deletions; pauses
    while viewing and resumes on the way back
  - Toggleable under **View → Preview pane**; visibility and the left splitter
    position persist via `QSettings`
- **Test suite** (`tests/`): everything runs under `QT_QPA_PLATFORM=offscreen`,
  with the thumbnail cache and `QSettings` redirected to temporary directories so
  real configuration is never touched. Fixtures generate test images according to
  what the environment can write, and tests for unwritable formats skip themselves

#### Changed

- **The viewer no longer opens its own window**: it became a page of the main
  window's `QStackedWidget`, and the screen still shows nothing but the image
  - `Viewer` no longer decides its own fate; it emits an `exit_view` signal
    instead. Launching it directly (`acdseen photo.jpg`) behaves as before
  - Entering view mode disables the browser's `Del` / `Enter` / `F5` shortcuts,
    which would otherwise fire ahead of the viewer's own key handling

#### Fixed

- **Slideshow interval steps** (caught by the newly added test suite)
- **Clicking a symlinked directory in the tree jumped somewhere else**:
  `set_directory()` used `Path.resolve()`, which follows symlinks to the real
  path and then moved the tree selection to *that* path — visually, "click A,
  land on B". Now it only normalizes lexically (`os.path.abspath` +
  `expanduser`)
- Syncing the tree selection called `blockSignals()` on the wrong object
  (`currentChanged` is connected on the `selectionModel`, not the `QTreeView`),
  so `set_directory()` re-entered itself once

## [0.1.0] - 2026-08-02

Initial release: the core of the ACDSee 1.2x remake is in place.

### Added

- **Browser** (`browser.py`): folder tree on the left, thumbnails on the right,
  one directory at a time — no recursion, no catalog
  - Thumbnails load asynchronously, on demand, appearing as you scroll
  - Built-in file operations: rename (F2), delete (Del), copy/cut/paste,
    copy to… / move to…
  - Sorting by name / size / type / date modified, with names sorted naturally
    (IMG_2 before IMG_10)
  - Thumbnail size adjustable (`Ctrl++` / `Ctrl+-`, 6 steps); the folder tree
    can be hidden (F9)
  - Status bar showing the image count, selection count, and the current file's
    dimensions / size / timestamp
  - Window geometry, splitter positions, thumbnail size, sort order and last
    directory all persist via `QSettings`
- **Full-screen viewer** (`viewer.py`): the image is there when it opens, and
  paging has no delay
  - Two-stage decode: a 1024px preview first (JPEG DCT scaling, 4–8× faster),
    then a seamless swap to full resolution
  - Neighbors `±2` pre-read into an LRU cache, so a cache hit renders the whole
    frame at once
  - 17 zoom steps (0.05×–16×), anchored on the mouse; dragging switches to free
    zoom automatically
  - Slideshow with adjustable interval (1s–60s) that never skips a frame whose
    decode hasn't finished
  - OSD overlay with page number / filename / dimensions / size / zoom level,
    toggleable (I); action feedback flashes briefly
  - Deleting an image collapses the list accordingly and syncs the browser
    selection
- **Decode layer** (`loader.py`)
  - A separate thread pool for thumbnails plus a disk cache (key = path + mtime +
    size); changing directory voids in-flight tasks by generation
  - Full-image loads use a token mechanism to discard stale tasks; the
    full-resolution LRU holds 8 images
  - EXIF orientation respected (`setAutoTransform`)
  - Optional Pillow fallback for PCX / PCD / PSD and other formats Qt doesn't
    know, warmed up on the main thread to avoid a concurrent-import crash
- **Startup** (`main.py`): `python -m acdseen`, a directory argument, or a single
  image straight into full screen — and it remembers the last directory
- **Configuration** (`config.py`): thumbnail sizes, zoom steps, slideshow
  intervals, pre-read counts and other "feel" parameters, all in one place

### Supported formats

- Qt built-in: BMP, GIF, JPEG, PNG, TGA, TIFF, WebP, PBM/PGM/PPM, XBM, XPM, ICO, SVG
- Pillow fallback: PCX, PCD, PSD, JP2, AVIF, HEIC
