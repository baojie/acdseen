"""Small utility functions."""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from . import config


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024.0
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if n < 100 else f"{n:.0f} {unit}"
    return f"{n:.0f} GB"


def human_dims(w: int, h: int) -> str:
    mp = w * h / 1_000_000
    return f"{w}×{h}" + (f" ({mp:.1f}MP)" if mp >= 1 else "")


def format_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def is_image(path: Path) -> bool:
    return path.suffix.lower() in config.SUPPORTED


def list_images(directory: Path, sort_key: int = config.SORT_NAME,
                reverse: bool = False, seed: int = 0) -> list[Path]:
    """List the images in a directory, sorted as requested. Non-recursive --
    the original only ever showed one directory at a time.

    seed only matters for "random" sorting: a given seed always produces the
    same order, so a refresh() triggered by deleting an image won't reshuffle
    the whole grid. Use a new seed to get a new deal.
    """
    try:
        entries = [p for p in directory.iterdir() if p.is_file() and is_image(p)]
    except OSError:
        return []

    if sort_key == config.SORT_RANDOM:
        # sort by name first, then shuffle, so the same seed yields the same result on any filesystem
        entries.sort(key=lambda p: natural_key(p.name))
        random.Random(seed).shuffle(entries)
        if reverse:
            entries.reverse()
        return entries

    def key(p: Path):
        try:
            st = p.stat()
        except OSError:
            st = None
        if sort_key == config.SORT_SIZE:
            return (st.st_size if st else 0, natural_key(p.name))
        if sort_key == config.SORT_DATE:
            return (st.st_mtime if st else 0, natural_key(p.name))
        if sort_key == config.SORT_TYPE:
            return (p.suffix.lower(), natural_key(p.name))
        if sort_key in config.SORT_NEEDS_DIMS:
            w, h = image_size(p)
            metric = {config.SORT_PIXELS: w * h,
                      config.SORT_WIDTH: w,
                      config.SORT_HEIGHT: h}[sort_key]
            return (metric, natural_key(p.name))
        return natural_key(p.name)

    return sorted(entries, key=key, reverse=reverse)


# Reading the file header for dimensions is not cheap (hundreds of files means
# hundreds of opens), so cache by path + mtime. When the file changes its mtime
# changes, the key invalidates naturally, and no manual clearing is needed.
_DIMS_CACHE: dict[tuple[str, float], tuple[int, int]] = {}


def image_size(path: Path) -> tuple[int, int]:
    """Pixel width and height of an image. If it can't be read, treat as 0x0 --
    it sinks to the front of the sort without raising."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return (0, 0)
    ck = (str(path), mtime)
    hit = _DIMS_CACHE.get(ck)
    if hit is not None:
        return hit
    from .loader import image_dimensions      # deferred import: util shouldn't pull in Qt at import time
    dims = image_dimensions(path) or (0, 0)
    if len(_DIMS_CACHE) > 20000:              # just a runaway guard, not an LRU
        _DIMS_CACHE.clear()
    _DIMS_CACHE[ck] = dims
    return dims


def natural_key(name: str):
    """Natural sort: IMG_2 comes before IMG_10. ACDSee of that era didn't do it,
    but there's no excuse not to today."""
    import re
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]
