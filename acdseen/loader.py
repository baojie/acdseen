"""Image decoding: thumbnail thread pool, two-stage full-image loading, read-ahead.

Design notes (recreating the 1996 feel of "never seeing a loading indicator"):

1. Two-stage decoding. First use QImageReader.setScaledSize() to get a
   PREVIEW_EDGE-sized preview -- JPEG uses DCT scaling, 4-8x faster than full
   decoding -- and show it immediately; the same image's full size keeps
   decoding in a background thread and seamlessly replaces the preview when
   done. The open time the user perceives is the first stage's time.

2. Read-ahead. While parked on image i, the background decodes i±READ_AHEAD
   images into the LRU. Flipping pages hits the cache directly.

3. Thumbnails use a separate thread pool + disk cache, so they never compete
   with the viewer's threads.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import (QObject, QRunnable, QSize, Qt, QThreadPool, Signal,
                            Slot)
from PySide6.QtGui import QImage, QImageReader

from . import config

# Pillow is an optional dependency, a fallback for old formats Qt doesn't recognize, like PCX/PCD
try:
    from PIL import Image as PILImage
    HAVE_PIL = True
except ImportError:  # pragma: no cover - environment-dependent
    HAVE_PIL = False

_pil_lock = threading.Lock()
_pil_ready = False


def warmup() -> None:
    """Warm up Pillow's plugin registry on the main thread.

    This is required: the first PILImage.open() call lazy-imports all plugin
    modules, and if several worker threads hit that import at the same time it
    crashes (a shiboken seterror_argument fatal error). Do it once on the main
    thread at startup.
    """
    global _pil_ready
    if not HAVE_PIL or _pil_ready:
        return
    with _pil_lock:
        if not _pil_ready:
            try:
                PILImage.init()
            except Exception:
                pass
            _pil_ready = True


# PIL decoding is fully serialized. warmup() only guards the plugin registry's
# lazy-import; it can't guard the part inside PILImage.open() that probes each
# plugin in turn -- a corrupt file makes it try every plugin, and concurrent
# probing from multiple worker threads still segfaults (it always happens when
# more than one preview panel exists). This is the cold path taken only for
# formats Qt doesn't recognize, so the serialization cost is negligible.
_pil_decode_lock = threading.Lock()


def _read_with_pil(path: Path, max_edge: int | None) -> QImage | None:
    if not HAVE_PIL:
        return None
    warmup()
    with _pil_decode_lock:
        return _read_with_pil_locked(path, max_edge)


def _read_with_pil_locked(path: Path, max_edge: int | None) -> QImage | None:
    try:
        with PILImage.open(path) as im:
            has_alpha = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
            im = im.convert("RGBA" if has_alpha else "RGB")
            if max_edge and max(im.size) > max_edge:
                im.thumbnail((max_edge, max_edge), PILImage.Resampling.BILINEAR)

            # Don't use PIL.ImageQt -- it touches Qt bindings from worker
            # threads, which causes problems. Feed the raw bytes straight to
            # QImage, then copy() to detach from this buffer.
            w, h = im.size
            if has_alpha:
                data = im.tobytes("raw", "RGBA")
                qimg = QImage(data, w, h, w * 4, QImage.Format_RGBA8888)
            else:
                data = im.tobytes("raw", "RGB")
                qimg = QImage(data, w, h, w * 3, QImage.Format_RGB888)
            return qimg.copy()   # data can be reclaimed only after this
    except Exception:
        return None


def load_image(path: Path, max_edge: int | None = None) -> QImage | None:
    """Decode one image. When max_edge is set, ask the decoder to produce a
    downscaled version directly (much faster)."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)  # respect EXIF orientation
    size = reader.size()

    if max_edge and size.isValid() and max(size.width(), size.height()) > max_edge:
        w, h = size.width(), size.height()
        scale = max_edge / max(w, h)
        reader.setScaledSize(QSize(max(1, int(w * scale)), max(1, int(h * scale))))

    img = reader.read()
    if img.isNull():
        return _read_with_pil(path, max_edge)
    return img


def image_dimensions(path: Path) -> tuple[int, int] | None:
    """Read just the file header for dimensions, without decoding pixels. Used
    for the status bar."""
    size = QImageReader(str(path)).size()
    if size.isValid():
        return size.width(), size.height()
    return None


# ------------------------------------------------------------------ thumbnails
class _ThumbCache:
    """Disk thumbnail cache. key = path + mtime + size; if the file changes it
    invalidates automatically."""

    def __init__(self, root: Path):
        self.root = root

    def _key(self, path: Path, mtime: float, edge: int) -> Path:
        raw = f"{path.resolve()}|{mtime:.0f}|{edge}".encode()
        h = hashlib.sha1(raw).hexdigest()
        # two-level directory so a single directory doesn't hold tens of thousands of files
        return self.root / h[:2] / f"{h[2:]}.png"

    def get(self, path: Path, mtime: float, edge: int) -> QImage | None:
        f = self._key(path, mtime, edge)
        if f.exists():
            img = QImage(str(f))
            if not img.isNull():
                return img
        return None

    def put(self, path: Path, mtime: float, edge: int, img: QImage) -> None:
        f = self._key(path, mtime, edge)
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(f), "PNG")
        except OSError:
            pass  # failing to write the cache is not fatal

    def clear(self) -> None:
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)


class _ThumbSignals(QObject):
    done = Signal(object, object)   # (Path, QImage | None)


class _ThumbTask(QRunnable):
    def __init__(self, path: Path, edge: int, cache: _ThumbCache,
                 signals: _ThumbSignals, generation: int, current_gen):
        super().__init__()
        self.path, self.edge = path, edge
        self.cache, self.signals = cache, signals
        self.generation, self._current_gen = generation, current_gen
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        # the directory has changed, so nobody wants this task's result; just drop it
        if self.generation != self._current_gen():
            return
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            self.signals.done.emit(self.path, None)
            return

        img = self.cache.get(self.path, mtime, self.edge)
        if img is None:
            img = load_image(self.path, max_edge=self.edge)
            if img is not None and not img.isNull():
                img = img.scaled(self.edge, self.edge,
                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.cache.put(self.path, mtime, self.edge, img)
            else:
                img = None

        if self.generation == self._current_gen():
            self.signals.done.emit(self.path, img)


class ThumbnailLoader(QObject):
    """Thumbnail thread pool. The ready signal is emitted on the main thread."""

    ready = Signal(object, object)   # (Path, QImage | None)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = _ThumbCache(config.CACHE_DIR)
        self._pool = QThreadPool(self)
        # keep one core for the UI and viewer decoding; don't saturate the machine
        self._pool.setMaxThreadCount(max(2, QThreadPool.globalInstance().maxThreadCount() - 1))
        self._signals = _ThumbSignals()
        self._signals.done.connect(self.ready)
        self._generation = 0
        self._paused = False
        self._pending: list[tuple[Path, int]] = []

    def _gen(self) -> int:
        return self._generation

    def invalidate(self) -> None:
        """Call when changing directories: invalidate all in-flight tasks."""
        self._generation += 1
        self._pending.clear()
        self._pool.clear()

    def set_paused(self, paused: bool) -> None:
        """Yield while the viewer is open -- thumbnails, however important,
        shouldn't slow down the image being viewed."""
        if paused == self._paused:
            return
        self._paused = paused
        if not paused:
            pending, self._pending = self._pending, []
            for path, edge in pending:
                self._start(path, edge)

    def request(self, path: Path, edge: int) -> None:
        if self._paused:
            self._pending.append((path, edge))
        else:
            self._start(path, edge)

    def _start(self, path: Path, edge: int) -> None:
        self._pool.start(_ThumbTask(path, edge, self._cache,
                                    self._signals, self._generation, self._gen))

    def clear_disk_cache(self) -> None:
        self._cache.clear()

    def shutdown(self) -> None:
        self._generation += 1
        self._pool.clear()
        self._pool.waitForDone(2000)


# ------------------------------------------------------------------ full-image loading
class _FullSignals(QObject):
    preview = Signal(object, object, int)    # path, QImage, token
    full = Signal(object, object, int)
    failed = Signal(object, int)


class _FullTask(QRunnable):
    """Two-stage decoding for one image. With preview_only=True this is the
    lightweight variant used for read-ahead."""

    def __init__(self, path: Path, token: int, signals: _FullSignals,
                 current_token, want_preview: bool = True):
        super().__init__()
        self.path, self.token, self.signals = path, token, signals
        self._current = current_token
        self.want_preview = want_preview
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        if self.token != self._current():
            return

        dims = image_dimensions(self.path)
        big = dims is None or max(dims) > config.PREVIEW_EDGE

        # first stage: small image, get it on screen as fast as possible
        if self.want_preview and big:
            prev = load_image(self.path, max_edge=config.PREVIEW_EDGE)
            if self.token != self._current():
                return
            if prev is not None and not prev.isNull():
                self.signals.preview.emit(self.path, prev, self.token)

        # second stage: full size
        full = load_image(self.path, max_edge=None)
        if self.token != self._current():
            return
        if full is None or full.isNull():
            self.signals.failed.emit(self.path, self.token)
        else:
            self.signals.full.emit(self.path, full, self.token)


class ImageLoader(QObject):
    """Loader used by the viewer: two-stage + LRU + read-ahead."""

    preview_ready = Signal(object, object)   # path, QImage
    full_ready = Signal(object, object)
    load_failed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(2, QThreadPool.globalInstance().maxThreadCount() // 2))
        self._sig = _FullSignals()
        self._sig.preview.connect(self._on_preview)
        self._sig.full.connect(self._on_full)
        self._sig.failed.connect(self._on_failed)
        self._token = 0
        self._current: Path | None = None
        self._lru: OrderedDict[Path, QImage] = OrderedDict()
        self._inflight: set[Path] = set()

    # -- cache --
    def _cache_put(self, path: Path, img: QImage) -> None:
        self._lru[path] = img
        self._lru.move_to_end(path)
        while len(self._lru) > config.FULL_CACHE_SIZE:
            self._lru.popitem(last=False)

    def cached(self, path: Path) -> QImage | None:
        img = self._lru.get(path)
        if img is not None:
            self._lru.move_to_end(path)
        return img

    def drop(self, path: Path) -> None:
        self._lru.pop(path, None)

    # -- main entry --
    def load(self, path: Path) -> QImage | None:
        """Request that an image be shown. Returns the QImage synchronously on a
        cache hit (zero-latency page turns)."""
        self._token += 1
        self._current = path

        hit = self.cached(path)
        if hit is not None:
            return hit

        self._pool.start(_FullTask(path, self._token, self._sig,
                                   lambda: self._token, want_preview=True))
        return None

    def read_ahead(self, paths: list[Path]) -> None:
        """Silently decode the neighbours. Skip ones already cached or in flight."""
        for p in paths:
            if p in self._lru or p in self._inflight:
                continue
            self._inflight.add(p)
            # read-ahead tasks don't emit preview and aren't affected by token invalidation (fixed token)
            task = _FullTask(p, -1, self._sig, lambda: -1, want_preview=False)
            self._pool.start(task)

    # -- callbacks --
    def _on_preview(self, path: Path, img: QImage, token: int) -> None:
        if token == self._token and path == self._current:
            self.preview_ready.emit(path, img)

    def _on_full(self, path: Path, img: QImage, token: int) -> None:
        self._inflight.discard(path)
        self._cache_put(path, img)
        if path == self._current:
            self.full_ready.emit(path, img)

    def _on_failed(self, path: Path, token: int) -> None:
        self._inflight.discard(path)
        if token == self._token and path == self._current:
            self.load_failed.emit(path)

    def shutdown(self) -> None:
        self._token += 1
        self._pool.clear()
        self._pool.waitForDone(2000)
