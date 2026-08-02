"""入口。

用法：
    acdseen              打开上次的目录（没有就是当前目录）
    acdseen ~/Pictures   打开指定目录的浏览器
    acdseen photo.jpg    直接全屏看这张图，并把同目录其他图排进列表
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from . import config
from .loader import warmup
from .util import is_image, list_images


USAGE = """\
用法: acdseen [目录 | 图片]

  acdseen              打开上次的目录（没有就是当前目录）
  acdseen ~/Pictures   打开指定目录的浏览器
  acdseen photo.jpg    直接全屏看这张图，同目录其他图自动排进列表

选项:
  -h, --help       显示此帮助
  -V, --version    显示版本
"""


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv

    # 在建 QApplication 之前处理，否则 --help 会开出一个窗口来
    for flag in argv[1:]:
        if flag in ("-h", "--help"):
            print(USAGE, end="")
            return 0
        if flag in ("-V", "--version"):
            from . import __version__
            print(f"{config.APP_NAME} {__version__}")
            return 0

    app = QApplication(argv)
    warmup()   # 主线程预热解码器，必须在任何工作线程起来之前
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.ORG_NAME)
    app.setApplicationDisplayName(config.APP_NAME)

    from . import theme
    s = QSettings(config.ORG_NAME, config.APP_NAME)
    on = s.value("win95_look", config.DEFAULT_WIN95_LOOK, type=bool)
    theme.apply(app, on)

    args = [a for a in argv[1:] if not a.startswith("-")]
    target = Path(args[0]).expanduser() if args else None

    # 直接给了一张图 —— 跳过浏览器，立刻全屏。这是最常用的路径，
    # 也是"启动到出图"这条延迟链上唯一该被优化的场景。
    if target and target.is_file() and is_image(target):
        from .viewer import Viewer
        directory = target.parent
        files = list_images(directory)
        index = files.index(target) if target in files else 0
        v = Viewer(files, index)
        v.showFullScreen()
        # 独立模式下没有可返回的浏览页，Esc 就是退出
        v.exit_view.connect(lambda _p: v.close())
        v.closed.connect(lambda _p: app.quit())
        return app.exec()

    if target and target.is_dir():
        start = target
    else:
        last = QSettings(config.ORG_NAME, config.APP_NAME).value("last_dir", type=str)
        start = Path(last) if last and Path(last).is_dir() else Path.cwd()

    from .browser import Browser
    w = Browser(start)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
