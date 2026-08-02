"""图像解码：缩略图线程池、全图两段式加载、预读。

设计要点（还原 1996 年那种"永远不出现加载中"的手感）：

1. 两段式解码。先用 QImageReader.setScaledSize() 拿一张 PREVIEW_EDGE 边长的
   预览——JPEG 走 DCT 缩放，比全解码快 4-8 倍——立刻上屏；同一张图的全尺寸
   在后台线程继续解，解完无缝替换。用户感知到的打开时间是第一段的时间。

2. 预读。停在第 i 张时，后台把 i±READ_AHEAD 全部解好塞进 LRU。翻页时直接命中。

3. 缩略图走独立线程池 + 磁盘缓存，和看图器的线程互不抢占。
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

# Pillow 是可选依赖，只为 PCX/PCD 这些 Qt 不认的老格式兜底
try:
    from PIL import Image as PILImage
    HAVE_PIL = True
except ImportError:  # pragma: no cover - 环境相关
    HAVE_PIL = False

_pil_lock = threading.Lock()
_pil_ready = False


def warmup() -> None:
    """在主线程预热 Pillow 的插件注册表。

    必须做：PILImage.open() 首次调用会 lazy-import 全部插件模块，多个
    工作线程同时撞上这个 import 会炸（表现为 shiboken 的 seterror_argument
    fatal error）。启动时在主线程一次性做掉。
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


# PIL 解码整条串行。warmup() 只挡住了插件注册表的 lazy-import，挡不住
# PILImage.open() 内部逐个插件试探的那一段 —— 损坏文件会把所有插件都试一遍，
# 多个工作线程同时试探照样段错误（在 preview 面板不止一个时必现）。
# 这是 Qt 认不出的格式才走的冷路径，串行的代价可以忽略。
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

            # 不走 PIL.ImageQt —— 它在工作线程里碰 Qt binding 会出问题。
            # 直接把原始字节喂给 QImage，再 copy() 脱离这块 buffer。
            w, h = im.size
            if has_alpha:
                data = im.tobytes("raw", "RGBA")
                qimg = QImage(data, w, h, w * 4, QImage.Format_RGBA8888)
            else:
                data = im.tobytes("raw", "RGB")
                qimg = QImage(data, w, h, w * 3, QImage.Format_RGB888)
            return qimg.copy()   # data 在此之后才可被回收
    except Exception:
        return None


def load_image(path: Path, max_edge: int | None = None) -> QImage | None:
    """解一张图。max_edge 非空时请求解码器直接吐缩小版（快得多）。"""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)  # 尊重 EXIF 方向
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
    """只读文件头拿尺寸，不解码像素。用于状态栏。"""
    size = QImageReader(str(path)).size()
    if size.isValid():
        return size.width(), size.height()
    return None


# ------------------------------------------------------------------ 缩略图
class _ThumbCache:
    """磁盘缩略图缓存。key = 路径 + mtime + 尺寸，文件变了自动失效。"""

    def __init__(self, root: Path):
        self.root = root

    def _key(self, path: Path, mtime: float, edge: int) -> Path:
        raw = f"{path.resolve()}|{mtime:.0f}|{edge}".encode()
        h = hashlib.sha1(raw).hexdigest()
        # 两级目录，避免单目录塞几万个文件
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
            pass  # 缓存写不进去不是致命错误

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
        # 目录已经换了，这个任务的结果没人要了，直接扔
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
    """缩略图线程池。ready 信号在主线程发出。"""

    ready = Signal(object, object)   # (Path, QImage | None)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache = _ThumbCache(config.CACHE_DIR)
        self._pool = QThreadPool(self)
        # 留一个核给 UI 和看图器解码，别把机器榨干
        self._pool.setMaxThreadCount(max(2, QThreadPool.globalInstance().maxThreadCount() - 1))
        self._signals = _ThumbSignals()
        self._signals.done.connect(self.ready)
        self._generation = 0
        self._paused = False
        self._pending: list[tuple[Path, int]] = []

    def _gen(self) -> int:
        return self._generation

    def invalidate(self) -> None:
        """切目录时调用：让所有在飞的任务作废。"""
        self._generation += 1
        self._pending.clear()
        self._pool.clear()

    def set_paused(self, paused: bool) -> None:
        """看图器打开时让路 —— 缩略图再重要也不该拖慢正在看的那张图。"""
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


# ------------------------------------------------------------------ 全图加载
class _FullSignals(QObject):
    preview = Signal(object, object, int)    # path, QImage, token
    full = Signal(object, object, int)
    failed = Signal(object, int)


class _FullTask(QRunnable):
    """一张图的两段式解码。preview_only=True 时用于预读的轻量档。"""

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

        # 第一段：小图，尽快上屏
        if self.want_preview and big:
            prev = load_image(self.path, max_edge=config.PREVIEW_EDGE)
            if self.token != self._current():
                return
            if prev is not None and not prev.isNull():
                self.signals.preview.emit(self.path, prev, self.token)

        # 第二段：全尺寸
        full = load_image(self.path, max_edge=None)
        if self.token != self._current():
            return
        if full is None or full.isNull():
            self.signals.failed.emit(self.path, self.token)
        else:
            self.signals.full.emit(self.path, full, self.token)


class ImageLoader(QObject):
    """看图器用的加载器：两段式 + LRU + 预读。"""

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

    # -- 缓存 --
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

    # -- 主入口 --
    def load(self, path: Path) -> QImage | None:
        """请求显示某张图。命中缓存时同步返回 QImage（零延迟翻页）。"""
        self._token += 1
        self._current = path

        hit = self.cached(path)
        if hit is not None:
            return hit

        self._pool.start(_FullTask(path, self._token, self._sig,
                                   lambda: self._token, want_preview=True))
        return None

    def read_ahead(self, paths: list[Path]) -> None:
        """把邻居悄悄解好。已缓存或在飞的跳过。"""
        for p in paths:
            if p in self._lru or p in self._inflight:
                continue
            self._inflight.add(p)
            # 预读任务不发 preview，也不受 token 作废影响（用固定 token）
            task = _FullTask(p, -1, self._sig, lambda: -1, want_preview=False)
            self._pool.start(task)

    # -- 回调 --
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
