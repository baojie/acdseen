"""Test fixtures.

Two things must be isolated:
  * Thumbnail disk cache -- otherwise tests write into the user's ~/.cache
  * QSettings   -- otherwise tests alter the user's real window geometry / last directory
Both are redirected to temporary directories at session scope.
"""

from __future__ import annotations

import os
import time

# Must be set before importing any Qt module
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from acdseen import config, i18n
from acdseen.loader import warmup

# Image matrix used by tests: format x size, with sizes straddling both sides of PREVIEW_EDGE
_SPECS = [
    ("IMG_000.jpg", 1920, 1080),
    ("IMG_001.png", 800, 600),
    ("IMG_002.bmp", 2400, 1800),   # > PREVIEW_EDGE, two-stage path
    ("IMG_003.gif", 320, 240),     # < PREVIEW_EDGE, single-stage
    ("IMG_004.tiff", 1600, 900),
    ("IMG_005.png", 640, 480),
    ("IMG_006.jpg", 2560, 1440),
    ("IMG_007.bmp", 500, 500),
    ("IMG_010.jpg", 800, 600),     # to verify natural sort: 10 should come after 7
]


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    warmup()
    yield app


@pytest.fixture(scope="session", autouse=True)
def _isolate(tmp_path_factory, qapp):
    """Redirect cache and settings to temp dirs so the user's real environment is untouched."""
    cache = tmp_path_factory.mktemp("cache")
    config.CACHE_DIR = cache / "thumbs"

    settings_dir = tmp_path_factory.mktemp("settings")
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(settings_dir))
    yield


@pytest.fixture(autouse=True)
def _clean_settings(_isolate):
    """Clear QSettings before each test.

    Browser.closeEvent writes back sort order, thumbnail size, and the last
    directory; without clearing, the previous test's state leaks into the next
    Browser's _restore_state(), showing up as mysterious ordering corruption.
    """
    QSettings(config.ORG_NAME, config.APP_NAME).clear()
    # Language state is a module-level variable and must be isolated too --
    # otherwise an English-locale CI would push the default language to en
    # and every test asserting Chinese text would fail.
    i18n.set_language(i18n.LANG_ZH)
    yield
    QSettings(config.ORG_NAME, config.APP_NAME).clear()


def _qt_can_write(suffix: str) -> bool:
    from PySide6.QtGui import QImageWriter
    fmt = suffix.lstrip(".").lower().encode()
    return fmt in QImageWriter.supportedImageFormats()


def _draw_qt(path, w, h) -> None:
    img = QImage(w, h, QImage.Format_RGB888)
    img.fill(QColor((w * 7) % 256, (h * 11) % 256, 128))
    p = QPainter(img)
    p.setPen(Qt.white)
    # Draw some content so encoders don't crush solid-color images into pathological tiny files
    for i in range(0, w, max(1, w // 20)):
        p.drawLine(i, 0, w - i, h)
    p.end()
    assert img.save(str(path)), f"无法写出 {path}"


def _draw_pil(path, w, h) -> bool:
    """Formats Qt can't write (GIF never, TIFF depends on qtimageformats)
    fall back to Pillow. Returns False if Pillow isn't installed, and the
    caller skips that one."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False
    im = Image.new("RGB", (w, h), ((w * 7) % 256, (h * 11) % 256, 128))
    dr = ImageDraw.Draw(im)
    for i in range(0, w, max(1, w // 20)):
        dr.line([(i, 0), (w - i, h)], fill=(255, 255, 255))
    im.save(path)
    return True


@pytest.fixture(scope="session")
def pics(tmp_path_factory, qapp):
    """A directory containing multiple formats and sizes, plus one corrupt file.

    How far format coverage goes depends on the environment: Qt can never
    write GIF, TIFF depends on the qtimageformats plugin, and only Pillow
    recognizes PCX. Formats that can't be written are simply not generated and
    the corresponding tests skip naturally -- better than the fixture blowing up.
    """
    d = tmp_path_factory.mktemp("pics")
    for name, w, h in _SPECS:
        target = d / name
        if _qt_can_write(target.suffix):
            _draw_qt(target, w, h)
        else:
            _draw_pil(target, w, h)

    # PCX: Qt never supports it, used purely to exercise the Pillow fallback path
    _draw_pil(d / "IMG_008.pcx", 1200, 900)

    # Deliberately corrupt file: must not crash and must be flagged as a decode failure
    (d / "broken.jpg").write_bytes(b"this is definitely not a jpeg")
    return d


@pytest.fixture
def workdir(pics, tmp_path):
    """A writable copy of pics -- tests that modify files use this, so the session-scoped fixture isn't polluted."""
    import shutil
    d = tmp_path / "work"
    shutil.copytree(pics, d)
    return d


def pump(app, ms: int = 500, until=None) -> bool:
    """Spin the event loop for up to ms milliseconds; stop early when until() is True.

    Returns whether until was satisfied (always True when until is not given).
    """
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        if until is not None and until():
            return True
        time.sleep(0.005)
    app.processEvents()
    return until is None or bool(until())
