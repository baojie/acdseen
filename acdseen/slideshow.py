"""看图器的幻灯片与乱序播放。

间隔可以是任意秒数，0 表示"尽快"——上一张解完就立刻翻，不等墙钟。
乱序直接洗文件列表本身，导航 / 预读 / 删除全都不用改。

依赖宿主提供：_slideshow(QTimer) _slideshow_delay _shuffle _files
             _original_files _index _is_preview _image
             current next_image() _queue_read_ahead() _flash()
"""

from __future__ import annotations

import random

from PySide6.QtWidgets import QInputDialog

from . import config
from .i18n import tr


class SlideshowMixin:
    # ------------------------------------------------------------- 幻灯片
    @staticmethod
    def format_delay(delay: float) -> str:
        if delay <= 0:
            return tr("slideshow.asap")
        return tr("slideshow.seconds", delay)

    def _interval_ms(self) -> int:
        """0 秒不能真给 QTimer 传 0 —— 那是空转烧 CPU。给个最小节拍，
        配合 _slideshow_tick 里"没解完就不翻"的守卫，实际就是解完即翻。"""
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
        # 上一张还没解完就不要往前跑，否则观感是跳帧。
        # 0 秒档全靠这一条踩刹车。
        if self._is_preview and self._image is None:
            return
        self.next_image()

    def set_delay(self, delay: float) -> None:
        """设成任意秒数，0 表示尽快。"""
        self._slideshow_delay = max(config.SLIDESHOW_DELAY_MIN,
                                    min(config.SLIDESHOW_DELAY_MAX, float(delay)))
        if self._slideshow.isActive():
            self._slideshow.start(self._interval_ms())
        self._flash(tr("slideshow.delay_set", self.format_delay(self._slideshow_delay)))
        self.update()

    def _cycle_delay(self, direction: int) -> None:
        delays = config.SLIDESHOW_DELAYS
        # 当前值可能不在档位表里（用对话框设过任意值），退到最接近的那一档
        i = min(range(len(delays)), key=lambda j: abs(delays[j] - self._slideshow_delay))
        # 已经落在某一档上才移动，否则先归位到最接近的那档
        if abs(delays[i] - self._slideshow_delay) < 1e-9:
            i = max(0, min(len(delays) - 1, i + direction))
        self.set_delay(delays[i])

    def ask_delay(self) -> None:
        """弹对话框设任意间隔。0 = 尽快。"""
        value, ok = QInputDialog.getDouble(
            self, tr("slideshow.dialog_title"), tr("slideshow.dialog_prompt"),
            float(self._slideshow_delay),
            config.SLIDESHOW_DELAY_MIN, config.SLIDESHOW_DELAY_MAX, 1)
        if ok:
            self.set_delay(value)

    # ------------------------------------------------------------- 乱序
    def set_shuffle(self, on: bool) -> None:
        """乱序直接洗 self._files 本身，导航 / 预读 / 删除全都不用改。
        当前这张永远留在原地，切换顺序不会把你正在看的图换掉。"""
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
            # 还原原始顺序，但只留还在列表里的 —— 删掉的不能复活
            alive = set(self._files)
            self._files = [p for p in self._original_files if p in alive]
        self._index = self._files.index(cur) if cur in self._files else 0
        self._queue_read_ahead()
        self._flash(tr("shuffle.on") if on else tr("shuffle.off"))
        self.update()

    def toggle_shuffle(self) -> None:
        self.set_shuffle(not self._shuffle)

    def _reshuffle(self) -> None:
        """洗出新的一轮。放在跑完一轮之后，免得每轮都是同一个"随机"顺序。"""
        random.shuffle(self._files)
