"""小工具函数。"""

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
    """列出目录里的图片，按指定方式排序。不递归 —— 原版就是一次一个目录。

    seed 只对「随机」排序有意义：同一个 seed 排出来的顺序是固定的，
    所以删一张图触发的 refresh() 不会把整个网格重洗一遍。想换一副新
    牌就换个 seed。
    """
    try:
        entries = [p for p in directory.iterdir() if p.is_file() and is_image(p)]
    except OSError:
        return []

    if sort_key == config.SORT_RANDOM:
        # 先按名称定序再洗，保证同一个 seed 在任何文件系统上都排出同一个结果
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


# 读文件头拿尺寸不便宜（几百个文件就是几百次 open），按 路径+mtime 缓存一份。
# 文件变了 mtime 就变，key 自然失效，不用手动清。
_DIMS_CACHE: dict[tuple[str, float], tuple[int, int]] = {}


def image_size(path: Path) -> tuple[int, int]:
    """图片的像素宽高。读不出来就当 0×0 —— 排序时沉到最前，不抛异常。"""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return (0, 0)
    ck = (str(path), mtime)
    hit = _DIMS_CACHE.get(ck)
    if hit is not None:
        return hit
    from .loader import image_dimensions      # 延迟导入：util 不该在导入期拖上 Qt
    dims = image_dimensions(path) or (0, 0)
    if len(_DIMS_CACHE) > 20000:              # 只是个防失控的上限，不做 LRU
        _DIMS_CACHE.clear()
    _DIMS_CACHE[ck] = dims
    return dims


def natural_key(name: str):
    """自然排序：IMG_2 排在 IMG_10 前面。当年的 ACDSee 没做，但今天不做说不过去。"""
    import re
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]
