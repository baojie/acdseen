"""浏览器左下角的预览窗格 —— 当前选中图片的大图预览。

原版 ACDSee 1.x 的 Preview Pane 可以在左 / 底 / 右三个位置配置，
Mac 版 1.5.1 的默认布局就是左下角：目录树在上，预览在下。

做法和缩略图同源：后台线程解码 + generation 作废。但只开一个线程，
一次只看一张，绝不为预览抢看图器的 CPU。

解码目标跟着窗格大小走（原版行为：预览区一变尺寸就自动重载），
resize 用单发 QTimer 防抖，拖分割条不会疯狂解码。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (QObject, QRunnable, QRect, QThreadPool, QTimer,
                            Qt, Signal, Slot)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QImage, QPainter,
                           QPalette)
from PySide6.QtWidgets import QWidget

from .loader import image_dimensions, load_image
from .util import format_size, human_dims

# 给窗格尺寸加的余量：目标边长稍大一点，缩放时不用抠得那么紧
_EDGE_MARGIN = 40


class _PreviewSignals(QObject):
    ready = Signal(object, object, int)   # path, QImage | None, generation


class _PreviewTask(QRunnable):
    """解一张预览图。edge 按窗格大小给，解码器直接吐缩小版（快）。"""

    def __init__(self, path: Path, edge: int, signals: _PreviewSignals,
                 generation: int, current_gen):
        super().__init__()
        self.path, self.edge = path, edge
        self.signals = signals
        self.generation, self._current_gen = generation, current_gen
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        if self.generation != self._current_gen():
            return
        img = load_image(self.path, max_edge=self.edge)
        if self.generation == self._current_gen():
            self.signals.ready.emit(self.path, img, self.generation)


class PreviewPane(QWidget):
    """当前选中图片的预览。图居中且不放大，底行显示文件名与尺寸。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setAttribute(Qt.WA_OpaquePaintEvent)   # 每帧全重画，不闪

        self._path: Path | None = None
        self._img: QImage | None = None
        self._dims: tuple[int, int] | None = None   # 原图尺寸，不是预览图的
        self._error = False
        self._generation = 0
        self._paused = False

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)             # 预览一次只有一张
        self._signals = _PreviewSignals()
        self._signals.ready.connect(self._on_ready)

        # resize 防抖：尺寸稳定 200ms 后才重新解码
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._reload_current)

    def _gen(self) -> int:
        return self._generation

    # ------------------------------------------------------------- 对外接口
    def show_path(self, path: Path | None) -> None:
        """切到新的选中项。None 表示没有选中（空目录）。"""
        if path == self._path:
            return
        self._path = path
        # 只读文件头，不解码像素 —— 信息行要报原图尺寸，
        # 而 self._img 是按窗格大小缩过的，拿它的尺寸会报出错的数字。
        self._dims = image_dimensions(path) if path is not None else None
        self._invalidate()
        self._request()
        self.update()

    def clear(self) -> None:
        self.show_path(None)

    def set_paused(self, paused: bool) -> None:
        """看图器打开时让路：作废在飞任务；关掉后重新加载当前项。

        必须是个持续状态，不能只作废一次 —— 切到看图页会让本窗格收到
        resizeEvent，防抖定时器 200ms 后照样把解码拉起来，正好在看图器
        最需要 CPU 的时候。"""
        if paused == self._paused:
            return
        self._paused = paused
        self._resize_timer.stop()
        self._invalidate()
        if not paused:
            self._request()
        self.update()

    def shutdown(self) -> None:
        """宿主销毁前调用：停掉防抖定时器，作废并等解码线程收尾。"""
        self._paused = True      # 关窗途中还会有 resize，别再拉起新解码
        self._resize_timer.stop()
        self._invalidate()
        self._pool.waitForDone(1000)

    # ------------------------------------------------------------- 加载
    def _need_edge(self) -> int:
        return max(96, self.width(), self.height()) + _EDGE_MARGIN

    def _invalidate(self) -> None:
        self._generation += 1
        self._pool.clear()
        self._img = None
        self._error = False

    def _request(self) -> None:
        if self._path is None or self._paused:
            return
        self._pool.start(_PreviewTask(self._path, self._need_edge(),
                                      self._signals, self._generation, self._gen))

    def _reload_current(self) -> None:
        if self._path is not None:
            self._invalidate()
            self._request()

    def _on_ready(self, path: Path, img: QImage | None, generation: int) -> None:
        if generation != self._generation or path != self._path:
            return
        if img is None or img.isNull():
            self._error = True
        else:
            self._img = img
        self.update()

    # ------------------------------------------------------------- 绘制
    def paintEvent(self, ev) -> None:
        # 颜色全走调色板 —— 这样套上 Win95 外观时窗格跟着变灰白，
        # 不会在一片灰底里留一块突兀的黑
        pal = self.palette()
        p = QPainter(self)
        p.fillRect(self.rect(), pal.base())
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self._paint_sunken_frame(p, pal)

        info_h = self._info_height()
        img_area = QRect(2, 2, self.width() - 4, self.height() - info_h - 2)

        if self._path is None:
            self._paint_hint(p, "选择一张图片查看预览", img_area)
        elif self._error:
            self._paint_hint(p, f"无法解码：{self._path.name}", img_area)
        elif self._img is not None:
            self._paint_image(p, self._img, img_area)
        else:
            self._paint_hint(p, "解码中…", img_area)

        self._paint_info(p, self._info_line())

    def _paint_image(self, p: QPainter, img: QImage, area: QRect) -> None:
        iw, ih = img.width(), img.height()
        if iw <= 0 or ih <= 0:
            return
        s = min(area.width() / iw, area.height() / ih, 1.0)   # 不放大 —— 原版行为
        w, h = max(1, int(iw * s)), max(1, int(ih * s))
        x = area.x() + (area.width() - w) // 2
        y = area.y() + (area.height() - h) // 2
        p.drawImage(QRect(x, y, w, h), img)

    def _paint_hint(self, p: QPainter, text: str, area: QRect) -> None:
        f = QFont(); f.setPointSize(10); p.setFont(f)
        p.setPen(self.palette().color(QPalette.Disabled, QPalette.Text))
        p.drawText(area, Qt.AlignCenter, text)

    def _paint_sunken_frame(self, p: QPainter, pal) -> None:
        """Win95 的凹陷边：左上暗、右下亮。深色主题下这两色也自动跟着走。"""
        w, h = self.width(), self.height()
        p.save()
        p.setPen(pal.color(QPalette.Shadow))
        p.drawLine(0, 0, w - 1, 0); p.drawLine(0, 0, 0, h - 1)
        p.setPen(pal.color(QPalette.Light))
        p.drawLine(0, h - 1, w - 1, h - 1); p.drawLine(w - 1, 0, w - 1, h - 1)
        p.restore()

    def _info_line(self) -> str:
        if self._path is None:
            return ""
        path = self._path
        parts = [path.name]
        if self._dims:
            parts.append(human_dims(*self._dims))
        try:
            st = path.stat()
            parts.append(format_size(st.st_size))
        except OSError:
            pass
        return "   ".join(parts)

    def _info_height(self) -> int:
        f = QFont(); f.setPointSize(10)
        return QFontMetrics(f).height() + 12

    def _paint_info(self, p: QPainter, text: str) -> None:
        if not text:
            return
        f = QFont(); f.setPointSize(10); p.setFont(f)
        fm = QFontMetrics(f)
        h = self._info_height()
        pal = self.palette()
        bar = QRect(2, self.height() - h - 2, self.width() - 4, h)
        p.fillRect(bar, pal.window())
        p.setPen(pal.color(QPalette.WindowText))
        p.drawText(bar.adjusted(8, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft,
                   fm.elidedText(text, Qt.ElideMiddle, bar.width() - 16))

    def resizeEvent(self, ev) -> None:
        if not self._paused:
            self._resize_timer.start(200)
        super().resizeEvent(ev)
