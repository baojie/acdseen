"""全局常量与配置。

这里集中放"手感"参数——原版 ACDSee 的体验几乎全部来自这些数字的取舍。
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "ACDSeeN"
ORG_NAME = "acdseen"

# ---------------------------------------------------------------- 支持的格式
# 1996 年 ACDSee 1.2x 的原始清单：BMP GIF JPG PNG PCX TGA TIFF Photo-CD。
# 这里保留全部，另外补上 Qt 免费送的几个（PBM/XPM/WEBP）。
QT_FORMATS = {
    ".bmp", ".gif", ".jpg", ".jpeg", ".jpe", ".png", ".tga",
    ".tif", ".tiff", ".webp", ".pbm", ".pgm", ".ppm", ".xbm", ".xpm",
    ".ico", ".svg",
}
# Qt 不带，交给 Pillow 兜底的
PIL_FORMATS = {".pcx", ".pcd", ".ppm", ".psd", ".jp2", ".avif", ".heic"}

SUPPORTED = QT_FORMATS | PIL_FORMATS


# ---------------------------------------------------------------- 缩略图
THUMB_SIZES = (64, 96, 128, 160, 200, 256)
DEFAULT_THUMB_SIZE = 128
THUMB_LABEL_LINES = 2

# 磁盘缓存位置，遵循 XDG
CACHE_DIR = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
) / "acdseen" / "thumbs"


# ---------------------------------------------------------------- 看图器
# 预读：进入某张图后，后台悄悄把前后各 N 张解好放内存。
# 原版叫 "read-ahead decompression"，是翻页零延迟的全部秘密。
READ_AHEAD = 2
# 全尺寸图的内存缓存张数（LRU）
FULL_CACHE_SIZE = 8

# 两段式解码的第一段目标边长：先出这么大的预览，立刻上屏，再后台换全尺寸。
# 486 时代是逐行刷新，今天用 JPEG 的 DCT 缩放读取更快且更好看。
PREVIEW_EDGE = 1024

ZOOM_STEPS = (0.05, 0.08, 0.12, 0.17, 0.25, 0.33, 0.5, 0.67, 1.0,
              1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0)

SLIDESHOW_DELAYS = (1, 2, 3, 5, 10, 15, 30, 60)
DEFAULT_SLIDESHOW_DELAY = 4


# ---------------------------------------------------------------- 排序
SORT_NAME, SORT_SIZE, SORT_TYPE, SORT_DATE = range(4)
SORT_NAMES = {
    SORT_NAME: "名称",
    SORT_SIZE: "大小",
    SORT_TYPE: "类型",
    SORT_DATE: "修改日期",
}
