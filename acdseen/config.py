"""Global constants and configuration.

This is where the "feel" parameters live -- nearly all of the original
ACDSee's experience comes from the choices baked into these numbers.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "ACDSeeN"
ORG_NAME = "acdseen"

# ---------------------------------------------------------------- supported formats
# The original ACDSee 1.2x list from 1996: BMP GIF JPG PNG PCX TGA TIFF Photo-CD.
# Keep them all, and add the ones Qt gives for free (PBM/XPM/WEBP).
QT_FORMATS = {
    ".bmp", ".gif", ".jpg", ".jpeg", ".jpe", ".png", ".tga",
    ".tif", ".tiff", ".webp", ".pbm", ".pgm", ".ppm", ".xbm", ".xpm",
    ".ico", ".svg",
}
# Qt doesn't ship these; they're handled by Pillow
PIL_FORMATS = {".pcx", ".pcd", ".ppm", ".psd", ".jp2", ".avif", ".heic"}

SUPPORTED = QT_FORMATS | PIL_FORMATS


# ---------------------------------------------------------------- thumbnails
THUMB_SIZES = (64, 96, 128, 160, 200, 256)
DEFAULT_THUMB_SIZE = 128
THUMB_LABEL_LINES = 2

# disk cache location, following XDG
CACHE_DIR = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "acdseen" / "thumbs"


# ---------------------------------------------------------------- viewer
# Read-ahead: after entering an image, the background quietly decodes the N
# images before and after it into memory.
# The original called this "read-ahead decompression"; it's the whole secret of
# zero-latency page turns.
READ_AHEAD = 2
# number of full-size images kept in the memory cache (LRU)
FULL_CACHE_SIZE = 8

# Target edge length for the first stage of two-stage decoding: produce a
# preview this big, show it immediately, then swap in the full size from the
# background. The 486 era used progressive refresh; today JPEG's DCT scaling is
# both faster and better looking.
PREVIEW_EDGE = 1024

ZOOM_STEPS = (0.05, 0.08, 0.12, 0.17, 0.25, 0.33, 0.5, 0.67, 1.0,
              1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0)

# [ / ] slideshow steps. 0 = as fast as possible: flip as soon as the previous
# image is decoded, without waiting on wall-clock time.
SLIDESHOW_DELAYS = (0, 0.5, 1, 2, 3, 5, 10, 15, 30, 60)
# must be one of the SLIDESHOW_DELAYS values, otherwise the first [ / ] press jumps somewhere else
DEFAULT_SLIDESHOW_DELAY = 3
# the interval can be any value in this range (right-click "Slideshow delay..."), not limited to the steps above
SLIDESHOW_DELAY_MIN, SLIDESHOW_DELAY_MAX = 0.0, 3600.0
# 0 seconds can't literally run the timer at 0 interval -- that would peg a
# core. This minimum tick, combined with the guard that doesn't flip until the
# previous image is decoded, makes it feel like it flips the moment decoding
# finishes.
SLIDESHOW_ASAP_MS = 30


# ---------------------------------------------------------------- sorting
# Values are written to QSettings; only append, never renumber -- otherwise old configs read back as a different sort.
(SORT_NAME, SORT_SIZE, SORT_TYPE, SORT_DATE,
 SORT_PIXELS, SORT_WIDTH, SORT_HEIGHT, SORT_RANDOM) = range(8)
# values aren't display text, they're i18n ids -- the menu looks them up via tr(name)
SORT_NAMES = {
    SORT_NAME: "sort.name",
    SORT_SIZE: "sort.size",
    SORT_TYPE: "sort.type",
    SORT_DATE: "sort.date",
    SORT_PIXELS: "sort.pixels",
    SORT_WIDTH: "sort.width",
    SORT_HEIGHT: "sort.height",
    SORT_RANDOM: "sort.random",
}
# these need to read each file's image header to sort -- more expensive than stat(), so mark them in the menu
SORT_NEEDS_DIMS = {SORT_PIXELS, SORT_WIDTH, SORT_HEIGHT}


# ---------------------------------------------------------------- appearance
# The Win95 look is on by default -- this project is a recreation of that
# 1996-era software, and grey beveled borders suit it better than today's flat
# styles. It can be turned off via the View -> Windows 95 Look menu.
DEFAULT_WIN95_LOOK = True


# ---------------------------------------------------------------- browse views
VIEW_THUMBS, VIEW_LIST = range(2)
# values as above: i18n ids
VIEW_NAMES = {VIEW_THUMBS: "view.thumbnails", VIEW_LIST: "view.list"}
# edge length of the small thumbnail at the left of each row in list mode
LIST_THUMB_SIZE = 40
