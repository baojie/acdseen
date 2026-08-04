"""Slideshow and shuffled playback for the viewer.

The interval can be any number of seconds; 0 means "as soon as possible" --
advance the moment the previous image is decoded, without waiting on the wall
clock. Shuffle simply shuffles the file list itself, so navigation, read-ahead,
and deletion all keep working unchanged.

Expects the host to provide: _slideshow(QTimer) _slideshow_delay _shuffle _files
                             _original_files _index _is_preview _image
                             current next_image() _queue_read_ahead() _flash()
"""

from __future__ import annotations

import random

from PySide6.QtWidgets import QInputDialog

from . import config
from .i18n import tr


class SlideshowMixin:
    # ------------------------------------------------------------- Slideshow
    @staticmethod
    def format_delay(delay: float) -> str:
        if delay <= 0:
            return tr("slideshow.asap")
        return tr("slideshow.seconds", delay)

    def _interval_ms(self) -> int:
        """QTimer can't actually be given 0 seconds -- that would spin the CPU.
        Use a minimum tick, combined with the "don't advance until decoded" guard
        in _slideshow_tick, which in practice means advance as soon as decoded."""
        if self._slideshow_delay <= 0:
            return config.SLIDESHOW_ASAP_MS
        return int(self._slideshow_delay * 1000)

    def toggle_slideshow(self) -> None:
        if self._slideshow.isActive():
            self._slideshow.stop()
            self._flash(tr("slideshow.stopped"))
        else:
            self._slideshow.start(self._interval_ms())
            order = tr("slideshow.shuffled") if self._shuffle else ""
            self._flash(tr("slideshow.running",
                           self.format_delay(self._slideshow_delay), order))
        self.update()

    def _slideshow_tick(self) -> None:
        # Don't advance while the previous image is still decoding, otherwise it
        # looks like skipped frames. The 0-second mode relies entirely on this brake.
        if self._is_preview and self._image is None:
            return
        self.next_image()

    def set_delay(self, delay: float) -> None:
        """Set to any number of seconds; 0 means as soon as possible."""
        self._slideshow_delay = max(config.SLIDESHOW_DELAY_MIN,
                                    min(config.SLIDESHOW_DELAY_MAX, float(delay)))
        if self._slideshow.isActive():
            self._slideshow.start(self._interval_ms())
        self._flash(tr("slideshow.delay_set", self.format_delay(self._slideshow_delay)))
        self.update()

    def _cycle_delay(self, direction: int) -> None:
        delays = config.SLIDESHOW_DELAYS
        # The current value may not be in the preset table (a dialog can set an arbitrary value); fall back to the nearest preset
        i = min(range(len(delays)), key=lambda j: abs(delays[j] - self._slideshow_delay))
        # Only move if it already sits on a preset; otherwise first snap to the nearest preset
        if abs(delays[i] - self._slideshow_delay) < 1e-9:
            i = max(0, min(len(delays) - 1, i + direction))
        self.set_delay(delays[i])

    def ask_delay(self) -> None:
        """Pop up a dialog to set an arbitrary interval. 0 = as soon as possible."""
        value, ok = QInputDialog.getDouble(
            self, tr("slideshow.dialog_title"), tr("slideshow.dialog_prompt"),
            float(self._slideshow_delay),
            config.SLIDESHOW_DELAY_MIN, config.SLIDESHOW_DELAY_MAX, 1)
        if ok:
            self.set_delay(value)

    # ------------------------------------------------------------- Shuffle
    def set_shuffle(self, on: bool) -> None:
        """Shuffle shuffles self._files itself, so navigation, read-ahead, and
        deletion all keep working unchanged. The current image always stays in
        place; toggling order won't swap out the image you're viewing."""
        on = bool(on)
        if on == self._shuffle:
            return
        self._shuffle = on
        cur = self.current
        if on:
            rest = [p for p in self._files if p != cur]
            random.shuffle(rest)
            self._files = ([cur] if cur is not None else []) + rest
        else:
            # Restore the original order, but keep only what's still in the list -- deleted files must not come back
            alive = set(self._files)
            self._files = [p for p in self._original_files if p in alive]
        self._index = self._files.index(cur) if cur in self._files else 0
        self._queue_read_ahead()
        self._flash(tr("shuffle.on") if on else tr("shuffle.off"))
        self.update()

    def toggle_shuffle(self) -> None:
        self.set_shuffle(not self._shuffle)

    def _reshuffle(self) -> None:
        """Shuffle out a new round. Done after a round finishes, so each round isn't the same "random" order."""
        random.shuffle(self._files)
