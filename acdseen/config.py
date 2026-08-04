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

# [ / ] 循环的档位。0 = 尽快：上一张解完就立刻翻，不等墙钟。
SLIDESHOW_DELAYS = (0, 0.5, 1, 2, 3, 5, 10, 15, 30, 60)
# 必须是 SLIDESHOW_DELAYS 里的值，否则第一次按 [ / ] 会跳到别处
DEFAULT_SLIDESHOW_DELAY = 3
# 间隔可以在这个范围内任取（右键「幻灯间隔…」），不限于上面的档位
SLIDESHOW_DELAY_MIN, SLIDESHOW_DELAY_MAX = 0.0, 3600.0
# 0 秒不能真的用 0 间隔跑定时器 —— 那会把一个核烧满。
# 用这个最小节拍配合"上一张没解完就不翻"的守卫，实际观感就是解完即翻。
SLIDESHOW_ASAP_MS = 30


# ---------------------------------------------------------------- 排序
# 数值会写进 QSettings，只能往后追加，不能重排 —— 否则老配置读出来是别的排序。
(SORT_NAME, SORT_SIZE, SORT_TYPE, SORT_DATE,
 SORT_PIXELS, SORT_WIDTH, SORT_HEIGHT, SORT_RANDOM) = range(8)
# 值不是显示文本，是 i18n 的 id —— 菜单里 tr(name) 再查表
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
# 这几种要读每个文件的图片头才能排 —— 比 stat() 贵，菜单上标出来
SORT_NEEDS_DIMS = {SORT_PIXELS, SORT_WIDTH, SORT_HEIGHT}


# ---------------------------------------------------------------- 外观
# Win95 外观默认开着 —— 这个项目复刻的就是 1996 年那套东西，
# 灰底立体边框比今天的扁平样式更对味。菜单「查看 → Windows 95 外观」可关。
DEFAULT_WIN95_LOOK = True


# ---------------------------------------------------------------- 浏览视图
VIEW_THUMBS, VIEW_LIST = range(2)
# 值同上：i18n 的 id
VIEW_NAMES = {VIEW_THUMBS: "view.thumbnails", VIEW_LIST: "view.list"}
# 列表模式每行左边那个小缩略图的边长
LIST_THUMB_SIZE = 40
