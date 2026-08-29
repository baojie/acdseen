"""The application icon: a photo with a magnifier over it.

Drawn the same way as the icons in `theme.py` -- one cell at a time on a
character grid, not with polygons. Two grids rather than one, because a 32x32
icon shrunk to 16x16 turns the magnifier into mud: at 16 the lens is a 5x5
ring with its corners knocked off, which the eye still reads as round next to
the square frame. Everything larger (the dock, the alt-tab switcher) scales up
from the 32x32 grid by an integer factor with nearest-neighbor, so the pixels
stay square instead of blurring.

The palette is the Win95 one: a black outline, flat fills, no gradients and no
anti-aliasing anywhere.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

# k black outline / w white / c sky / y sun / G far hill / l near hill
# p lens glass / d handle shaft / . transparent
_COLORS = {
    "k": "#000000", "w": "#ffffff", "c": "#00a0e0", "y": "#ffff00",
    "G": "#008000", "l": "#00c000", "p": "#a0d0f0", "d": "#808080",
}

ICON_32 = (
    "................................",
    "................................",
    "kkkkkkkkkkkkkkkkkkkkkkkkkk......",
    "kwwwwwwwwwwwwwwwwwwwwwwwwk......",
    "kwccccccccccccccccccccccwk......",
    "kwccccccccccccccyyycccccwk......",
    "kwcccccccccccccyyyyyccccwk......",
    "kwcccccccccccccyyyyyccccwk......",
    "kwcccccccccccccyyyyyccccwk......",
    "kwccccccccccccccyyycccccwk......",
    "kwccccccccccccccccccccccwk......",
    "kwccccccccccccccccccccccwk......",
    "kwccccccGcccccccccccccccwk......",
    "kwcccccGGGccccccccccccccwk......",
    "kwccccGGGGGcccccccckkkkkkk......",
    "kwcccGGGGGGGcccccckkkppkkk......",
    "kwccGGGGGGGGGcccckkwwwpppkk.....",
    "kwcGGGGGGGGGGGcckkwwppppppkk....",
    "kwGGGGGGGGGGGGGlkkwpppppppkk....",
    "kwGGGGGGGGGGGGllkppppppppppk....",
    "kwGGGGGGGGGGGlllkppppppppppk....",
    "kwGGGGGGGGGGllllkkppppppppkk....",
    "kwGGGGGGGGGlllllkkpppppppkddk...",
    "kwGGGGGGGGlllllllkkppppppkkddk..",
    "kwwwwwwwwwwwwwwwwwkkkppkkk.kddk.",
    "kkkkkkkkkkkkkkkkkkkkkkkkkk..kddk",
    ".............................kkk",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

# The 16x16 cut: no white mat around the photo, a smaller sun, and a magnifier
# that has moved off the frame's corner so its ring does not merge with the
# frame's own black border.
ICON_16 = (
    "................",
    "kkkkkkkkkkkkk...",
    "kccccccccccck...",
    "kcccccccyycck...",
    "kcccccccyycck...",
    "kccGcccccccck...",
    "kcGGGccccccck...",
    "kGGGGGcccccck...",
    "kGGGGGGllllkkk..",
    "kGGGGGGGllkwppk.",
    "kGGGGGGGGlkpppk.",
    "kkkkkkkkkkkpppk.",
    "...........kkk..",
    "..............kk",
    "...............k",
    "................",
)


def _from_grid(grid: tuple[str, ...], scale: int) -> QPixmap:
    """Paint one grid cell per `scale`x`scale` block -- integer scaling only."""
    side = len(grid) * scale
    pm = QPixmap(side, side)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            color = _COLORS.get(ch)
            if color:
                p.fillRect(x * scale, y * scale, scale, scale, QColor(color))
    p.end()
    return pm


def pixmap(size: int) -> QPixmap:
    """The icon at `size` pixels. Only the smallest sizes use the 16x16 grid;
    24 already has room for the detailed one, shrunk."""
    if size < 24:
        pm = _from_grid(ICON_16, max(1, size // 16))
    else:
        pm = _from_grid(ICON_32, max(1, size // 32))
    if pm.width() != size:
        # Only for sizes that are not a multiple of the grid (48 is the common
        # one). Smooth here: a nearest-neighbor 64->48 drops every fourth
        # column and eats whole features.
        pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pm


def app_icon() -> QIcon:
    """The window / taskbar icon, with a pixmap for each size Qt may ask for."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(pixmap(size))
    return icon


def export_png(path: Path, size: int) -> None:
    """Write one PNG, for installing into the desktop icon theme."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap(size).save(str(path), "PNG")
