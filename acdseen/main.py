"""Entry point.

Usage:
    acdseen              open the last directory (or the current directory if none)
    acdseen ~/Pictures   open the browser on the given directory
    acdseen photo.jpg    view this image fullscreen immediately, with the other
                         images in the same directory queued into the list
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from . import config, i18n

from .loader import warmup
from .util import is_image, list_images


def _init_language() -> None:
    """Determine the UI language: read the last selection, falling back to the system locale."""
    s = QSettings(config.ORG_NAME, config.APP_NAME)
    saved = s.value("language", type=str)
    i18n.set_language(saved if saved in i18n.LANG_NAMES else i18n.system_default())


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv

    _init_language()

    # Handle this before creating QApplication, otherwise --help would pop up a window
    for flag in argv[1:]:
        if flag in ("-h", "--help"):
            print(i18n.tr("usage"), end="")
            return 0
        if flag in ("-V", "--version"):
            from . import __version__
            print(f"{config.APP_NAME} {__version__}")
            return 0

    app = QApplication(argv)
    warmup()   # warm up the decoder on the main thread; must run before any worker thread starts
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName(config.ORG_NAME)
    app.setApplicationDisplayName(config.APP_NAME)

    from . import theme
    s = QSettings(config.ORG_NAME, config.APP_NAME)
    on = s.value("win95_look", config.DEFAULT_WIN95_LOOK, type=bool)
    theme.apply(app, on)

    args = [a for a in argv[1:] if not a.startswith("-")]
    target = Path(args[0]).expanduser() if args else None

    # Given an image directly -- skip the browser and go fullscreen immediately.
    # This is the most common path, and the only scene on the "startup to image"
    # latency chain worth optimizing.
    if target and target.is_file() and is_image(target):
        from .viewer import Viewer
        directory = target.parent
        files = list_images(directory)
        index = files.index(target) if target in files else 0
        v = Viewer(files, index)
        v.showFullScreen()
        # In standalone mode there is no browser page to return to, so Esc exits
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
