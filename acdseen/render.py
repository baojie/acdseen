"""看图器的绘制：图像本体 + OSD 叠层。

原版 Viewer 屏幕上除了图什么都没有，所以这里没有工具栏也没有状态栏，
信息全走左下角那个可开关的半透明叠层。

依赖宿主提供：_pixmap _scaled _scaled_for _image _error _offset
             _show_osd _transient _osd_timer _index _files _is_preview
             _shuffle _slideshow _slideshow_delay
             current _effective_scale() format_delay() _invalidate_scaled()
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter

from . import config
from .i18n import tr
from .util import format_size, human_dims


class RenderMixin:
    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(24, 24, 26))

        if self._error:
            p.setPen(QColor(220, 90, 90))
            f = QFont(); f.setPointSize(13); p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, self._error)
            self._paint_osd(p)
            return

        if self._pixmap is not None:
            scale = self._effective_scale()
            iw = max(1, int(self._pixmap.width() * scale))
            ih = max(1, int(self._pixmap.height() * scale))

            # 缩小时预先重采样一次并缓存，之后每帧只是 blit
            key = (round(scale, 4), iw, ih)
            if self._scaled_for != key:
                # 缩小、以及 2 倍以内的放大都用平滑插值 —— "缩放到显示框"
                # 基本都落在这个区间，用最近邻会糊成马赛克。
                # 再往上是在看像素，最近邻反而更快也更该保留原样。
                mode = Qt.FastTransformation if scale > 2.0 else Qt.SmoothTransformation
                if abs(scale - 1.0) < 1e-6:
                    self._scaled = self._pixmap
                else:
                    self._scaled = self._pixmap.scaled(iw, ih, Qt.IgnoreAspectRatio, mode)
                self._scaled_for = key

            x = (self.width() - iw) // 2 + self._offset.x()
            y = (self.height() - ih) // 2 + self._offset.y()
            p.drawPixmap(x, y, self._scaled)

        self._paint_osd(p)

    def _paint_osd(self, p: QPainter) -> None:
        lines: list[str] = []
        if self._show_osd and self.current:
            path = self.current
            info = [f"[{self._index + 1}/{len(self._files)}]", path.name]
            if self._image:
                info.append(human_dims(self._image.width(), self._image.height()))
            try:
                info.append(format_size(path.stat().st_size))
            except OSError:
                pass
            info.append(f"{self._effective_scale() * 100:.0f}%")
            if self._is_preview and self._image is not None:
                info.append(tr("osd.refining"))
            if self._slideshow.isActive():
                info.append(tr("osd.play", self.format_delay(self._slideshow_delay)))
            if self._shuffle:
                info.append(tr("osd.shuffle"))
            lines.append("   ".join(info))

        if self._transient:
            lines.append(self._transient)

        if not lines:
            return

        p.setRenderHint(QPainter.TextAntialiasing)
        f = QFont(); f.setPointSize(10); p.setFont(f)
        fm = p.fontMetrics()
        pad, gap = 8, 4
        w = max(fm.horizontalAdvance(t) for t in lines) + pad * 2
        h = len(lines) * fm.height() + pad * 2 + (len(lines) - 1) * gap
        box = QRect(12, self.height() - h - 12, w, h)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 165))
        p.drawRoundedRect(box, 4, 4)
        p.setPen(QColor(235, 235, 235))
        y = box.top() + pad + fm.ascent()
        for t in lines:
            p.drawText(box.left() + pad, y, t)
            y += fm.height() + gap

    def _flash(self, text: str, msec: int = 1200) -> None:
        self._transient = text
        self._osd_timer.start(msec)
        self.update()

    def _hide_transient_osd(self) -> None:
        self._transient = None
        self.update()

    def _update_title(self) -> None:
        if self.current:
            self.window().setWindowTitle(f"{self.current.name} — {config.APP_NAME}")

    def resizeEvent(self, ev) -> None:
        self._invalidate_scaled()
        super().resizeEvent(ev)
