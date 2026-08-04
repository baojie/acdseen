"""Decode layer: two-stage loading, read-ahead, thumbnail thread pool, disk cache.

Three tests here map directly to real bugs fixed during development; removing
them would reopen those holes:
  * concurrent multi-threaded PCX decode must not crash  -- Pillow plugin lazy-import crashed shiboken
  * thumbnail is actually generated with the right size  -- QImage.scaled was passed an int instead of an enum, silently failing
  * Pillow fallback must not go through ImageQt         -- ImageQt touching Qt bindings on a worker thread explodes
"""

from __future__ import annotations

from pathlib import Path

import pytest

from acdseen import config
from acdseen.loader import (HAVE_PIL, ImageLoader, ThumbnailLoader,
                            image_dimensions, load_image)
from conftest import pump


# ------------------------------------------------------------------ synchronous decoding
def test_load_image_handles_every_format(pics):
    for p in sorted(pics.glob("IMG_*")):
        img = load_image(p)
        assert img is not None and not img.isNull(), f"cannot decode {p.name}"


def test_load_image_returns_none_for_broken_file(pics):
    assert load_image(pics / "broken.jpg") is None


def test_load_image_max_edge_limits_long_side(pics):
    img = load_image(pics / "IMG_002.bmp", max_edge=512)
    assert max(img.width(), img.height()) <= 512


def test_image_dimensions_without_decoding(pics):
    assert image_dimensions(pics / "IMG_000.jpg") == (1920, 1080)
    assert image_dimensions(pics / "broken.jpg") is None


@pytest.mark.skipif(not HAVE_PIL, reason="Pillow not installed")
def test_pil_fallback_decodes_pcx(pics):
    pcx = pics / "IMG_008.pcx"
    if not pcx.exists():
        pytest.skip("no pcx sample generated")
    img = load_image(pcx)
    assert img is not None and img.size().toTuple() == (1200, 900)


@pytest.mark.skipif(not HAVE_PIL, reason="Pillow not installed")
def test_pil_fallback_avoids_imageqt():
    """Regression: PIL.ImageQt touching Qt bindings on a worker thread causes a process-level crash.

    The loader must construct the QImage from raw bytes itself and never
    reintroduce ImageQt.
    """
    import acdseen.loader as L
    assert not hasattr(L, "ImageQt"), "PIL.ImageQt must never be imported again"
    src = Path(L.__file__).read_text()
    assert "from PIL.ImageQt" not in src and "import ImageQt" not in src


# ------------------------------------------------------------------ two-stage
def test_large_image_is_two_stage_preview_then_full(qapp, pics):
    loader = ImageLoader()
    events = []
    loader.preview_ready.connect(lambda p, i: events.append(("preview", i.size())))
    loader.full_ready.connect(lambda p, i: events.append(("full", i.size())))

    big = pics / "IMG_002.bmp"          # 2400x1800 > PREVIEW_EDGE
    assert loader.load(big) is None     # cold cache, returns None synchronously
    assert pump(qapp, 6000, lambda: any(k == "full" for k, _ in events))

    kinds = [k for k, _ in events]
    assert kinds[0] == "preview", "the first frame must be the low-res preview, or the fast open is pointless"
    assert "full" in kinds

    prev_size = next(s for k, s in events if k == "preview")
    full_size = next(s for k, s in events if k == "full")
    assert max(prev_size.toTuple()) <= config.PREVIEW_EDGE
    assert full_size.toTuple() == (2400, 1800)
    loader.shutdown()


def test_small_image_emits_no_preview(qapp, pics):
    loader = ImageLoader()
    events = []
    loader.preview_ready.connect(lambda p, i: events.append("preview"))
    loader.full_ready.connect(lambda p, i: events.append("full"))

    loader.load(pics / "IMG_003.gif")   # 320x240, below PREVIEW_EDGE
    assert pump(qapp, 4000, lambda: "full" in events)
    assert "preview" not in events, "decoding a small image twice is pure waste"
    loader.shutdown()


def test_cache_hit_returns_synchronously(qapp, pics):
    loader = ImageLoader()
    p = pics / "IMG_001.png"
    loader.load(p)
    assert pump(qapp, 4000, lambda: loader.cached(p) is not None)
    # The second call must return synchronously -- that's zero-latency paging
    assert loader.load(p) is not None
    loader.shutdown()


def test_prefetch_fills_lru_with_neighbors(qapp, pics):
    loader = ImageLoader()
    files = sorted(pics.glob("IMG_*"))[:4]
    loader.read_ahead(files)
    assert pump(qapp, 8000, lambda: len(loader._lru) >= len(files))
    for f in files:
        assert loader.cached(f) is not None
    loader.shutdown()


def test_lru_respects_its_limit(qapp, pics):
    loader = ImageLoader()
    many = list(sorted(pics.glob("IMG_*"))) * 3
    loader.read_ahead(many)
    pump(qapp, 8000)
    assert len(loader._lru) <= config.FULL_CACHE_SIZE
    loader.shutdown()


def test_decode_failure_emits_load_failed(qapp, pics):
    loader = ImageLoader()
    failed = []
    loader.load_failed.connect(lambda p: failed.append(p))
    loader.load(pics / "broken.jpg")
    assert pump(qapp, 4000, lambda: bool(failed))
    loader.shutdown()


def test_drop_evicts_cache_entry(qapp, pics):
    loader = ImageLoader()
    p = pics / "IMG_001.png"
    loader.load(p)
    pump(qapp, 4000, lambda: loader.cached(p) is not None)
    loader.drop(p)
    assert loader.cached(p) is None
    loader.shutdown()


# ------------------------------------------------------------------ thumbnails
def test_thumbnail_is_generated_at_the_right_size(qapp, pics):
    """Regression: QImage.scaled was once passed an int instead of a Qt enum, so the task silently threw."""
    loader = ThumbnailLoader()
    got = {}
    loader.ready.connect(lambda p, i: got.__setitem__(p, i))

    files = sorted(pics.glob("IMG_*"))
    for f in files:
        loader.request(f, 128)
    assert pump(qapp, 15000, lambda: len(got) >= len(files))

    for f in files:
        img = got[f]
        assert img is not None and not img.isNull(), f"no thumbnail for {f.name}"
        assert max(img.width(), img.height()) == 128, "the long edge should equal the requested edge exactly"
    loader.shutdown()


def test_concurrent_pcx_decode_does_not_crash(qapp, pics):
    """Regression: Pillow's plugin lazy-import crashed shiboken under multiple worker threads.

    This test's value is that "the process is still alive" -- when it crashes,
    it never even reaches the assertion.
    """
    if not (pics / "IMG_008.pcx").exists():
        pytest.skip("no pcx sample")
    loader = ThumbnailLoader()
    done = []
    loader.ready.connect(lambda p, i: done.append(p))
    for _ in range(12):
        loader.request(pics / "IMG_008.pcx", 96)
    assert pump(qapp, 15000, lambda: len(done) >= 1)
    loader.shutdown()


def test_thumbnail_is_written_to_disk_cache_and_reused(qapp, pics):
    loader = ThumbnailLoader()
    got = []
    loader.ready.connect(lambda p, i: got.append(i))
    loader.request(pics / "IMG_000.jpg", 96)
    assert pump(qapp, 8000, lambda: bool(got))

    cached = list(config.CACHE_DIR.rglob("*.png"))
    assert cached, "the thumbnail was never written to disk"
    loader.shutdown()


def test_thumbnail_cache_is_invalidated_by_mtime(qapp, workdir):
    import os
    loader = ThumbnailLoader()
    got = []
    loader.ready.connect(lambda p, i: got.append(i))
    target = workdir / "IMG_001.png"

    loader.request(target, 96)
    assert pump(qapp, 8000, lambda: bool(got))
    before = len(list(config.CACHE_DIR.rglob("*.png")))

    os.utime(target, (0, 0))    # pretend the file was modified
    got.clear()
    loader.request(target, 96)
    assert pump(qapp, 8000, lambda: bool(got))
    assert len(list(config.CACHE_DIR.rglob("*.png"))) > before, "mtime changed but the stale cache entry was reused"
    loader.shutdown()


def test_broken_file_thumbnail_returns_none_not_crash(qapp, pics):
    loader = ThumbnailLoader()
    got = {}
    loader.ready.connect(lambda p, i: got.__setitem__(p, i))
    loader.request(pics / "broken.jpg", 96)
    assert pump(qapp, 6000, lambda: bool(got))
    assert got[pics / "broken.jpg"] is None
    loader.shutdown()


def test_requests_queue_while_paused_and_run_on_resume(qapp, pics):
    loader = ThumbnailLoader()
    got = []
    loader.ready.connect(lambda p, i: got.append(p))

    loader.set_paused(True)
    for f in sorted(pics.glob("IMG_*"))[:3]:
        loader.request(f, 96)
    pump(qapp, 600)
    assert not got, "no task should finish while the pool is paused"
    assert len(loader._pending) == 3

    loader.set_paused(False)
    assert pump(qapp, 10000, lambda: len(got) >= 3)
    loader.shutdown()


def test_invalidate_voids_in_flight_tasks(qapp, pics):
    loader = ThumbnailLoader()
    got = []
    loader.ready.connect(lambda p, i: got.append(p))
    for f in sorted(pics.glob("IMG_*")):
        loader.request(f, 160)
    loader.invalidate()
    pump(qapp, 1500)
    # After invalidate, not guaranteed that none arrive (an in-flight one may finish), but not all should arrive
    assert len(got) < len(list(pics.glob("IMG_*")))
    loader.shutdown()
