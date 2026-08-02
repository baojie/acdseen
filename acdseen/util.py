"""小工具函数。"""

from __future__ import annotations

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
                reverse: bool = False) -> list[Path]:
    """列出目录里的图片，按指定方式排序。不递归 —— 原版就是一次一个目录。"""
    try:
        entries = [p for p in directory.iterdir() if p.is_file() and is_image(p)]
    except OSError:
        return []

    def key(p: Path):
        try:
            st = p.stat()
        except OSError:
            st = None
        if sort_key == config.SORT_SIZE:
            return (st.st_size if st else 0, p.name.lower())
        if sort_key == config.SORT_DATE:
            return (st.st_mtime if st else 0, p.name.lower())
        if sort_key == config.SORT_TYPE:
            return (p.suffix.lower(), p.name.lower())
        return natural_key(p.name)

    return sorted(entries, key=key, reverse=reverse)


def natural_key(name: str):
    """自然排序：IMG_2 排在 IMG_10 前面。当年的 ACDSee 没做，但今天不做说不过去。"""
    import re
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]
