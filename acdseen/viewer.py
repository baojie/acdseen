"""全屏看图器 —— ACDSee Image Viewer 的复刻。

原版的灵魂：打开即见图，翻页无延迟，手不离键盘，屏幕上除了图什么都没有。
所以这里没有工具栏、没有侧边栏，信息全部走可开关的 OSD 叠层。
"""

from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QColor, QFont, QImage, QKeySequence,
                           QPainter, QPixmap)
from PySide6.QtWidgets import (QApplication, QInputDialog, QMenu, QMessageBox,
                               QWidget)

from . import config
from .loader import ImageLoader
from .util import format_size, human_dims

# FIT_WINDOW 是原版行为：小图不放大，一张 200px 的图在全屏下还是 200px。
# FIT_FILL 是"真的铺满"：小图也放大到贴住显示框的短边。
FIT_WINDOW, FIT_WIDTH, FIT_ONE_TO_ONE, FIT_FREE, FIT_FILL = range(5)

FIT_NAMES = {
    FIT_WINDOW: "适应窗口",
    FIT_WIDTH: "适应宽度",
    FIT_ONE_TO_ONE: "实际大小 1:1",
    FIT_FILL: "缩放到显示框",
}


class Viewer(QWidget):
    """看图视图。持有一份文件列表，自己负责在其中前后移动。

    既能当独立窗口（`acdseen photo.jpg` 直接开图），也能嵌进浏览器的
    QStackedWidget 当一页用。区别只在于谁来响应 exit_view：
    独立时是退出程序，嵌入时是切回缩略图页。
    """

    exit_view = Signal(object)       # 请求退出查看，带上当前路径
    closed = Signal(object)          # 窗口真的被关掉了（仅独立模式）
    file_deleted = Signal(object)

    def __init__(self, files: list[Path], index: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(config.APP_NAME)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)

        self._files = list(files)
        self._index = max(0, min(index, len(self._files) - 1))

        self._image: QImage | None = None
        self._pixmap: QPixmap | None = None
        self._is_preview = False          # 当前显示的是不是第一段的低清图
        self._error: str | None = None

        # 默认铺满显示框：单页看图和幻灯放映都该占满窗口，小图也放大。
        # 想要原版那种"小图不放大"，按 * 切到 FIT_WINDOW。
        self._fit_mode = FIT_FILL
        self._base_fit = FIT_FILL     # 手动缩放后翻页要回到的模式
        self._prev_fit = FIT_FILL     # 中键从 1:1 切回来时要回到的模式
        self._scale = 1.0
        self._offset = QPoint(0, 0)       # 图像相对视口中心的平移
        self._drag_from: QPoint | None = None
        self._drag_offset = QPoint(0, 0)

        # 缩放后的位图缓存，避免每帧重采样大图
        self._scaled: QPixmap | None = None
        self._scaled_for: tuple[float, int, int] | None = None

        self._show_osd = True
        self._osd_timer = QTimer(self)
        self._osd_timer.setSingleShot(True)
        self._osd_timer.timeout.connect(self._hide_transient_osd)
        self._transient: str | None = None

        self._slideshow = QTimer(self)
        self._slideshow.timeout.connect(self._slideshow_tick)
        self._slideshow_delay: float = config.DEFAULT_SLIDESHOW_DELAY
        self._shuffle = False
        self._original_files = list(files)   # 关掉乱序时按这个还原

        self._loader = ImageLoader(self)
        self._loader.preview_ready.connect(self._on_preview)
        self._loader.full_ready.connect(self._on_full)
        self._loader.load_failed.connect(self._on_failed)

        self.resize(1000, 720)
        self._goto(self._index, initial=True)

    # ------------------------------------------------------------- 属性
    @property
    def current(self) -> Path | None:
        if 0 <= self._index < len(self._files):
            return self._files[self._index]
        return None

    # ------------------------------------------------------------- 导航
    def _goto(self, index: int, initial: bool = False) -> None:
        if not self._files:
            self.exit_view.emit(None)
            return
        self._index = index % len(self._files)
        path = self._files[self._index]

        self._error = None
        self._invalidate_scaled()

        img = self._loader.load(path)
        if img is not None:
            # 缓存命中：这一帧就是全尺寸，翻页零延迟
            self._set_image(img, preview=False)
        else:
            # 没命中：保留上一张画面，等 preview 信号回来再换。
            # 关键——绝不清屏，绝不显示"加载中"。
            self._is_preview = True

        self._update_title()
        self._queue_read_ahead()
        if not initial:
            self.update()

    def _queue_read_ahead(self) -> None:
        n = len(self._files)
        if n <= 1:
            return
        neighbours = []
        for d in range(1, config.READ_AHEAD + 1):
            neighbours.append(self._files[(self._index + d) % n])
            neighbours.append(self._files[(self._index - d) % n])
        self._loader.read_ahead(neighbours)

    def next_image(self) -> None:
        # 乱序跑完一轮就重洗，否则第二轮还是同一个顺序，等于没乱
        if self._shuffle and self._index + 1 >= len(self._files):
            self._reshuffle()
            self._goto(0)
            return
        self._goto(self._index + 1)

    def prev_image(self) -> None:
        self._goto(self._index - 1)

    def first_image(self) -> None:
        self._goto(0)

    def last_image(self) -> None:
        self._goto(len(self._files) - 1)

    # ------------------------------------------------------------- 加载回调
    def _on_preview(self, path: Path, img: QImage) -> None:
        if path == self.current:
            self._set_image(img, preview=True)

    def _on_full(self, path: Path, img: QImage) -> None:
        if path == self.current:
            # 无缝替换：只有缩放模式是"适应"时才需要重算，1:1 下位置保持
            self._set_image(img, preview=False, keep_view=True)

    def _on_failed(self, path: Path) -> None:
        if path == self.current:
            self._image = self._pixmap = self._scaled = None
            self._error = f"无法解码：{path.name}"
            self.update()

    def _set_image(self, img: QImage, preview: bool, keep_view: bool = False) -> None:
        was_preview = self._is_preview
        self._image = img
        self._pixmap = QPixmap.fromImage(img)
        self._is_preview = preview
        self._invalidate_scaled()

        # 从预览换成全尺寸时，视图参数（缩放模式、平移）保持不变
        if not (keep_view and not was_preview):
            if not keep_view:
                self._offset = QPoint(0, 0)
                if self._fit_mode == FIT_FREE:
                    self._fit_mode = self._base_fit
        self.update()

    # ------------------------------------------------------------- 缩放
    def _fitted_scale(self) -> float:
        if not self._image:
            return 1.0
        iw, ih = self._image.width(), self._image.height()
        if iw <= 0 or ih <= 0:
            return 1.0
        vw, vh = self.width(), self.height()
        if self._fit_mode == FIT_WINDOW:
            s = min(vw / iw, vh / ih)
            return min(s, 1.0)      # 小图不放大 —— 原版行为
        if self._fit_mode == FIT_FILL:
            # 该放大就放大：整张图贴住显示框，长宽比不变
            return min(vw / iw, vh / ih)
        if self._fit_mode == FIT_WIDTH:
            return vw / iw
        return 1.0

    def _effective_scale(self) -> float:
        if self._fit_mode == FIT_FREE:
            return self._scale
        return self._fitted_scale()

    def _set_fit(self, mode: int) -> None:
        self._fit_mode = mode
        if mode != FIT_FREE:
            # 记住这个模式：翻到下一张时回到它，而不是一律退回适应窗口。
            # 幻灯放映时选了"缩放到显示框"，就该每张都铺满。
            self._base_fit = mode
        self._offset = QPoint(0, 0)
        self._invalidate_scaled()
        self._flash(FIT_NAMES.get(mode, ""))
        self.update()

    def zoom_by(self, direction: int, anchor: QPoint | None = None) -> None:
        cur = self._effective_scale()
        steps = config.ZOOM_STEPS
        if direction > 0:
            nxt = next((s for s in steps if s > cur * 1.001), steps[-1])
        else:
            nxt = next((s for s in reversed(steps) if s < cur * 0.999), steps[0])

        # 以鼠标位置（或视口中心）为锚点缩放
        if anchor is not None and self._image:
            centre = QPoint(self.width() // 2, self.height() // 2)
            rel = anchor - centre - self._offset
            self._offset = self._offset - rel * (nxt / cur - 1.0)

        self._scale = nxt
        self._fit_mode = FIT_FREE
        self._invalidate_scaled()
        self._flash(f"{nxt * 100:.0f}%")
        self.update()

    def _invalidate_scaled(self) -> None:
        self._scaled = None
        self._scaled_for = None

    # ------------------------------------------------------------- 幻灯片
    @staticmethod
    def format_delay(delay: float) -> str:
        if delay <= 0:
            return "尽快"
        return f"{delay:g} 秒"

    def _interval_ms(self) -> int:
        """0 秒不能真给 QTimer 传 0 —— 那是空转烧 CPU。给个最小节拍，
        配合 _slideshow_tick 里"没解完就不翻"的守卫，实际就是解完即翻。"""
        if self._slideshow_delay <= 0:
            return config.SLIDESHOW_ASAP_MS
        return int(self._slideshow_delay * 1000)

    def toggle_slideshow(self) -> None:
        if self._slideshow.isActive():
            self._slideshow.stop()
            self._flash("幻灯片：停止")
        else:
            self._slideshow.start(self._interval_ms())
            order = "，乱序" if self._shuffle else ""
            self._flash(f"幻灯片：{self.format_delay(self._slideshow_delay)}/张{order}")
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
        self._flash(f"幻灯片间隔：{self.format_delay(self._slideshow_delay)}")
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
            self, "幻灯片间隔", "每张停留秒数（0 = 尽快）：",
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
        self._flash("乱序：开" if on else "乱序：关")
        self.update()

    def toggle_shuffle(self) -> None:
        self.set_shuffle(not self._shuffle)

    def _reshuffle(self) -> None:
        """洗出新的一轮。放在跑完一轮之后，免得每轮都是同一个"随机"顺序。"""
        random.shuffle(self._files)

    # ------------------------------------------------------------- 文件操作
    def delete_current(self) -> None:
        path = self.current
        if path is None:
            return
        if QMessageBox.question(
            self, "删除", f"删除 {path.name}？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        try:
            path.unlink()
        except OSError as e:
            QMessageBox.warning(self, "删除失败", str(e))
            return

        self._loader.drop(path)
        self.file_deleted.emit(path)
        del self._files[self._index]
        if not self._files:
            self.exit_view.emit(None)   # 删光了，没什么可看的了
            return
        self._goto(min(self._index, len(self._files) - 1))

    # ------------------------------------------------------------- 绘制
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
                info.append("· 精修中")
            if self._slideshow.isActive():
                info.append(f"▶ {self.format_delay(self._slideshow_delay)}")
            if self._shuffle:
                info.append("⤨ 乱序")
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

    # ------------------------------------------------------------- 输入
    def keyPressEvent(self, ev) -> None:
        k = ev.key()
        mods = ev.modifiers()

        if k in (Qt.Key_Space, Qt.Key_PageDown, Qt.Key_Right, Qt.Key_Down, Qt.Key_N):
            if self._fit_mode == FIT_FREE and k in (Qt.Key_Right, Qt.Key_Down):
                self._pan(-60 if k == Qt.Key_Right else 0, -60 if k == Qt.Key_Down else 0)
            else:
                self.next_image()
        elif k in (Qt.Key_Backspace, Qt.Key_PageUp, Qt.Key_Left, Qt.Key_Up, Qt.Key_P):
            if self._fit_mode == FIT_FREE and k in (Qt.Key_Left, Qt.Key_Up):
                self._pan(60 if k == Qt.Key_Left else 0, 60 if k == Qt.Key_Up else 0)
            else:
                self.prev_image()
        elif k == Qt.Key_Home:
            self.first_image()
        elif k == Qt.Key_End:
            self.last_image()
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_by(+1)
        elif k in (Qt.Key_Minus, Qt.Key_Underscore):
            self.zoom_by(-1)
        elif k == Qt.Key_Asterisk:
            self._set_fit(FIT_WINDOW)
        elif k == Qt.Key_Slash:
            self._set_fit(FIT_ONE_TO_ONE)
        elif k == Qt.Key_W:
            self._set_fit(FIT_WIDTH)
        elif k == Qt.Key_Z:
            self._set_fit(FIT_FILL)
        elif k in (Qt.Key_F, Qt.Key_Return, Qt.Key_Enter, Qt.Key_F11):
            self.toggle_fullscreen()
        elif k == Qt.Key_S:
            self.toggle_slideshow()
        elif k == Qt.Key_R:
            self.toggle_shuffle()
        elif k == Qt.Key_D:
            self.ask_delay()
        elif k == Qt.Key_BracketRight:
            self._cycle_delay(+1)
        elif k == Qt.Key_BracketLeft:
            self._cycle_delay(-1)
        elif k == Qt.Key_I:
            self._show_osd = not self._show_osd
            self.update()
        elif k == Qt.Key_Delete:
            self.delete_current()
        elif k == Qt.Key_Escape:
            if self.window().isFullScreen():
                self.window().showNormal()
            else:
                self.exit_view.emit(self.current)
        else:
            super().keyPressEvent(ev)

    def _pan(self, dx: int, dy: int) -> None:
        self._offset += QPoint(dx, dy)
        self.update()

    def toggle_fullscreen(self) -> None:
        # 作用于顶层窗口：嵌入浏览器时是主窗口，独立时就是自己
        win = self.window()
        win.showNormal() if win.isFullScreen() else win.showFullScreen()
        self._invalidate_scaled()

    def is_fullscreen(self) -> bool:
        return self.window().isFullScreen()

    def wheelEvent(self, ev) -> None:
        delta = ev.angleDelta().y()
        if ev.modifiers() & Qt.ControlModifier:
            self.zoom_by(1 if delta > 0 else -1, ev.position().toPoint())
        elif self._fit_mode == FIT_FREE:
            self._pan(0, 60 if delta > 0 else -60)
        else:
            self.prev_image() if delta > 0 else self.next_image()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            self._drag_from = ev.position().toPoint()
            self._drag_offset = QPoint(self._offset)
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, ev) -> None:
        if self._drag_from is not None:
            moved = ev.position().toPoint() - self._drag_from
            if self._fit_mode != FIT_FREE and moved.manhattanLength() > 3:
                # 一拖就自动切到自由缩放，否则拖了没反应很困惑
                self._scale = self._effective_scale()
                self._fit_mode = FIT_FREE
            self._offset = self._drag_offset + moved
            self.update()

    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            moved = (ev.position().toPoint() - (self._drag_from or QPoint())).manhattanLength()
            self._drag_from = None
            self.setCursor(Qt.ArrowCursor)
            if moved <= 3:
                self.next_image()   # 单击翻页
        elif ev.button() == Qt.MiddleButton:
            # 在"你选的适应模式"和 1:1 之间来回。不能直接读 _base_fit——
            # 切到 1:1 时它自己也会变成 1:1，那样就再也切不回来了。
            if self._fit_mode == FIT_ONE_TO_ONE:
                self._set_fit(self._prev_fit)
            else:
                self._prev_fit = self._base_fit
                self._set_fit(FIT_ONE_TO_ONE)

    def mouseDoubleClickEvent(self, ev) -> None:
        self.toggle_fullscreen()

    def contextMenuEvent(self, ev) -> None:
        m = QMenu(self)
        m.addAction("下一张\tSpace", self.next_image)
        m.addAction("上一张\tBackspace", self.prev_image)
        m.addSeparator()
        m.addAction("适应窗口\t*", lambda: self._set_fit(FIT_WINDOW))
        m.addAction("缩放到显示框\tZ", lambda: self._set_fit(FIT_FILL))
        m.addAction("适应宽度\tW", lambda: self._set_fit(FIT_WIDTH))
        m.addAction("实际大小\t/", lambda: self._set_fit(FIT_ONE_TO_ONE))
        m.addAction("全屏\tF", self.toggle_fullscreen)
        m.addSeparator()
        act = m.addAction("幻灯片\tS", self.toggle_slideshow)
        act.setCheckable(True); act.setChecked(self._slideshow.isActive())
        act = m.addAction("乱序\tR", self.toggle_shuffle)
        act.setCheckable(True); act.setChecked(self._shuffle)
        m.addAction(f"幻灯间隔…\tD（当前 {self.format_delay(self._slideshow_delay)}）",
                    self.ask_delay)
        m.addSeparator()
        m.addAction("删除\tDel", self.delete_current)
        m.addAction("返回浏览\tEsc", lambda: self.exit_view.emit(self.current))
        m.exec(ev.globalPos())

    def teardown(self) -> None:
        """停掉定时器和解码线程。宿主在丢弃这个视图前必须调用。"""
        self._slideshow.stop()
        self._loader.shutdown()

    def closeEvent(self, ev) -> None:
        self.teardown()
        self.closed.emit(self.current)
        super().closeEvent(ev)
