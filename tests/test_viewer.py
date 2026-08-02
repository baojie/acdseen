"""看图器：导航、缩放模式、幻灯片、容错。"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from acdseen import config
from acdseen.util import list_images
from acdseen.viewer import (FIT_FILL, FIT_FREE, FIT_ONE_TO_ONE, FIT_WIDTH, FIT_WINDOW,
                            Viewer)
from conftest import pump


def press(w, key, mods=Qt.NoModifier):
    QApplication.sendEvent(w, QKeyEvent(QKeyEvent.KeyPress, key, mods))


@pytest.fixture
def viewer(qapp, pics):
    files = [f for f in list_images(pics) if f.name != "broken.jpg"]
    v = Viewer(files, 0)
    v.resize(1000, 700)
    v.show()
    pump(qapp, 5000, lambda: v._image is not None)
    yield v
    v.close()
    pump(qapp, 200)


def test_首图解出来了(viewer):
    assert viewer._image is not None
    assert viewer._error is None


def test_空格翻页(qapp, viewer):
    first = viewer.current
    press(viewer, Qt.Key_Space)
    pump(qapp, 3000, lambda: viewer._image is not None)
    assert viewer.current != first


def test_退格回退(qapp, viewer):
    press(viewer, Qt.Key_Space)
    pump(qapp, 2000)
    press(viewer, Qt.Key_Backspace)
    pump(qapp, 2000)
    assert viewer._index == 0


def test_翻页环回(qapp, viewer):
    n = len(viewer._files)
    for _ in range(n):
        press(viewer, Qt.Key_Space)
        pump(qapp, 400)
    assert viewer._index == 0, "转一圈应回到起点"


def test_Home_End(qapp, viewer):
    press(viewer, Qt.Key_End)
    pump(qapp, 2000)
    assert viewer._index == len(viewer._files) - 1
    press(viewer, Qt.Key_Home)
    pump(qapp, 2000)
    assert viewer._index == 0


def test_翻页时不清屏(qapp, viewer):
    """核心手感：切到未缓存的图时，旧画面必须留在屏幕上直到新图解出来。"""
    before = viewer._image
    assert before is not None

    # 清空 LRU，保证目标图确实没缓存 —— 否则预读会让它同步命中，测不到这条路径
    viewer._loader._lru.clear()
    viewer._goto(len(viewer._files) - 1)

    assert viewer._image is before, "切图瞬间清了屏，会出现闪烁/白屏"
    assert pump(qapp, 5000, lambda: viewer._image is not before), "新图始终没解出来"


def test_预读命中时同步换成新图(qapp, viewer):
    """预读命中的另一面：不该保留旧图，应当立刻显示已缓存的新图。"""
    target = viewer._files[1]
    assert pump(qapp, 6000, lambda: viewer._loader.cached(target) is not None)
    before = viewer._image
    viewer._goto(1)
    assert viewer._image is not before
    assert not viewer._is_preview, "缓存命中拿到的应当是全尺寸，不是预览"


def test_默认就把小图铺满显示框(qapp, pics):
    """单页看图和幻灯放映都该占满窗口，不用先按 Z。"""
    small = pics / "IMG_003.gif"           # 320x240
    v = Viewer([small], 0)
    v.resize(1600, 1200)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    assert v._fit_mode == FIT_FILL, "默认就该是缩放到显示框"
    assert v._effective_scale() > 1.0, "小图默认就要放大"
    v.close()


def test_按星号切回原版的不放大(qapp, pics):
    """* 保留 ACDSee 原版行为：小图保持原始尺寸。"""
    small = pics / "IMG_003.gif"           # 320x240
    v = Viewer([small], 0)
    v.resize(1600, 1200)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    v._set_fit(FIT_WINDOW)
    assert v._effective_scale() == 1.0
    v.close()


def test_适应窗口缩小大图(qapp, pics):
    v = Viewer([pics / "IMG_002.bmp"], 0)  # 2400x1800
    v.resize(800, 600)
    v.show()
    pump(qapp, 5000, lambda: v._image is not None and not v._is_preview)
    assert v._effective_scale() < 1.0
    v.close()


def test_缩放档位(qapp, viewer):
    viewer._set_fit(FIT_ONE_TO_ONE)
    assert viewer._effective_scale() == 1.0
    viewer.zoom_by(+1)
    assert viewer._fit_mode == FIT_FREE
    assert viewer._effective_scale() > 1.0
    viewer.zoom_by(-1)
    assert viewer._effective_scale() == pytest.approx(1.0)


def test_缩放不越界(qapp, viewer):
    for _ in range(40):
        viewer.zoom_by(+1)
    assert viewer._effective_scale() == config.ZOOM_STEPS[-1]
    for _ in range(80):
        viewer.zoom_by(-1)
    assert viewer._effective_scale() == config.ZOOM_STEPS[0]


def test_缩放模式快捷键(qapp, viewer):
    press(viewer, Qt.Key_Slash)
    assert viewer._fit_mode == FIT_ONE_TO_ONE
    press(viewer, Qt.Key_W)
    assert viewer._fit_mode == FIT_WIDTH
    press(viewer, Qt.Key_Asterisk)
    assert viewer._fit_mode == FIT_WINDOW


def test_自由缩放下方向键平移而非翻页(qapp, viewer):
    viewer.zoom_by(+1)
    idx, off = viewer._index, viewer._offset.x()
    press(viewer, Qt.Key_Right)
    assert viewer._index == idx, "放大状态下右键应平移，不该翻页"
    assert viewer._offset.x() != off


def test_适应模式下方向键翻页(qapp, viewer):
    viewer._set_fit(FIT_WINDOW)
    press(viewer, Qt.Key_Right)
    pump(qapp, 1500)
    assert viewer._index == 1


def test_幻灯片开关(qapp, viewer):
    assert not viewer._slideshow.isActive()
    press(viewer, Qt.Key_S)
    assert viewer._slideshow.isActive()
    press(viewer, Qt.Key_S)
    assert not viewer._slideshow.isActive()


def test_幻灯片间隔可调(qapp, viewer):
    base = viewer._slideshow_delay
    viewer._cycle_delay(+1)
    assert viewer._slideshow_delay > base
    viewer._cycle_delay(-1)
    assert viewer._slideshow_delay == base


def test_信息条开关(qapp, viewer):
    on = viewer._show_osd
    press(viewer, Qt.Key_I)
    assert viewer._show_osd is not on


def test_预读在翻页后填充(qapp, viewer):
    pump(qapp, 6000, lambda: len(viewer._loader._lru) >= 2)
    assert len(viewer._loader._lru) >= 2, "预读没生效，翻页会卡"


def test_损坏文件标记错误不崩溃(qapp, pics):
    v = Viewer([pics / "broken.jpg"], 0)
    v.show()
    assert pump(qapp, 5000, lambda: v._error is not None)
    assert v._image is None
    v.repaint()          # 错误态也必须能画出来
    v.close()


def test_删除后跳到下一张(qapp, workdir, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    files = [f for f in list_images(workdir) if f.name != "broken.jpg"]
    n = len(files)
    v = Viewer(files, 0)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)

    doomed = v.current
    v.delete_current()
    pump(qapp, 2000)

    assert not doomed.exists()
    assert len(v._files) == n - 1
    assert v.current != doomed
    v.close()


def test_删除最后一张后请求退出(qapp, tmp_path, pics, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    lone = tmp_path / "only.png"
    lone.write_bytes((pics / "IMG_001.png").read_bytes())

    v = Viewer([lone], 0)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)

    exits = []
    v.exit_view.connect(lambda p: exits.append(p))
    v.delete_current()
    pump(qapp, 500)

    assert not lone.exists()
    assert exits == [None], "删光了必须请求退出，否则停在空白页"
    v.close()


def test_Esc请求退出而不是自己关掉(qapp, viewer):
    """看图器不决定自己的去留 —— 嵌在浏览器里是返回，独立开是退出。"""
    exits = []
    viewer.exit_view.connect(lambda p: exits.append(p))
    press(viewer, Qt.Key_Escape)
    assert exits == [viewer.current]
    assert viewer.isVisible(), "不该自作主张关掉自己"


def test_全屏时Esc先退全屏(qapp, viewer):
    viewer.toggle_fullscreen()
    pump(qapp, 500)
    exits = []
    viewer.exit_view.connect(lambda p: exits.append(p))
    press(viewer, Qt.Key_Escape)
    pump(qapp, 500)
    assert not exits, "第一次 Esc 应该只退全屏"
    assert not viewer.is_fullscreen()


def test_全屏切换(qapp, viewer):
    viewer.toggle_fullscreen()
    pump(qapp, 300)
    assert viewer.is_fullscreen()
    viewer.toggle_fullscreen()
    pump(qapp, 300)
    assert not viewer.is_fullscreen()


def test_关闭时发出closed信号(qapp, pics):
    files = [f for f in list_images(pics) if f.name != "broken.jpg"]
    v = Viewer(files, 1)
    v.show()
    pump(qapp, 3000, lambda: v._image is not None)
    seen = []
    v.closed.connect(lambda p: seen.append(p))
    expected = v.current
    v.close()
    pump(qapp, 300)
    assert seen == [expected], "浏览器靠这个信号同步选中项"


# ------------------------------------------------------------------ 幻灯片间隔
def test_间隔可设任意秒数(viewer):
    viewer.set_delay(2.5)
    assert viewer._slideshow_delay == 2.5
    assert viewer._interval_ms() == 2500


def test_零秒不给定时器传0(viewer):
    """真传 0 是空转烧 CPU。0 档给最小节拍，靠"没解完就不翻"踩刹车。"""
    viewer.set_delay(0)
    assert viewer._slideshow_delay == 0
    assert viewer._interval_ms() == config.SLIDESHOW_ASAP_MS > 0
    assert viewer.format_delay(0) == "尽快"


def test_零秒幻灯片跑起来且不跳帧(qapp, viewer):
    viewer.set_delay(0)
    viewer.toggle_slideshow()
    assert viewer._slideshow.isActive()
    start = viewer.current
    assert pump(qapp, 8000, lambda: viewer.current != start), "0 秒档应该真的往前翻"
    # 守卫：上一张还没解出来就不许往前跑
    viewer._is_preview, viewer._image = True, None
    before = viewer._index
    viewer._slideshow_tick()
    assert viewer._index == before, "没解完还翻，就是跳帧"
    viewer.toggle_slideshow()


def test_间隔超范围会夹住(viewer):
    viewer.set_delay(-5)
    assert viewer._slideshow_delay == config.SLIDESHOW_DELAY_MIN
    viewer.set_delay(99999)
    assert viewer._slideshow_delay == config.SLIDESHOW_DELAY_MAX


def test_档位循环含0秒(viewer):
    viewer.set_delay(config.SLIDESHOW_DELAYS[1])
    viewer._cycle_delay(-1)
    assert viewer._slideshow_delay == 0, "往下一档应该走到 0 秒"
    viewer._cycle_delay(-1)
    assert viewer._slideshow_delay == 0, "已经在头上了，不该越界"


def test_任意值按档位增减先归位(viewer):
    """用对话框设过 7 秒后按 ]，应该走到最接近的档位而不是乱跳。"""
    viewer.set_delay(7)
    viewer._cycle_delay(+1)
    assert viewer._slideshow_delay in config.SLIDESHOW_DELAYS
    assert viewer._slideshow_delay == 5, "7 最接近 5，先归位到 5"


# ------------------------------------------------------------------ 乱序
def test_乱序不换掉当前这张(viewer):
    cur = viewer.current
    viewer.set_shuffle(True)
    assert viewer._shuffle
    assert viewer.current == cur, "切乱序不该把你正在看的图换掉"
    assert set(viewer._files) == set(viewer._original_files), "一张都不能丢"


def test_关掉乱序还原原始顺序(viewer):
    original = list(viewer._files)
    viewer.set_shuffle(True)
    viewer.set_shuffle(False)
    assert viewer._files == original
    assert not viewer._shuffle


def test_乱序确实打乱了顺序(qapp, pics):
    """单次洗牌理论上可能洗回原样，多洗几次至少有一次不同。"""
    files = [f for f in list_images(pics) if f.name != "broken.jpg"]
    assert len(files) >= 5, "样本太少，这条测试没意义"
    changed = False
    for _ in range(20):
        v = Viewer(files, 0)
        v.set_shuffle(True)
        if v._files != files:
            changed = True
        v.teardown()
        if changed:
            break
    assert changed, "洗了 20 次一次都没变，随机没生效"


def test_乱序跑完一轮会重洗(qapp, viewer):
    viewer.set_shuffle(True)
    viewer._index = len(viewer._files) - 1     # 站在最后一张
    before = list(viewer._files)
    viewer.next_image()
    pump(qapp, 300)
    assert viewer._index == 0, "应该回到新一轮的第一张"
    assert set(viewer._files) == set(before), "重洗不能丢图"


def test_乱序时删图不会让文件复活(qapp, workdir, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    files = [f for f in list_images(workdir) if f.name != "broken.jpg"]
    v = Viewer(files, 0)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)

    v.set_shuffle(True)
    doomed = v.current
    v.delete_current()
    pump(qapp, 300)
    v.set_shuffle(False)                       # 还原时按的是 _original_files
    assert doomed not in v._files, "删掉的图不能靠关乱序复活"
    assert len(v._files) == len(files) - 1
    v.close()


# ------------------------------------------------------------------ 缩放到显示框
def _small_pic(tmp_path):
    """一张远小于窗口的图，用来区分「适应窗口」和「缩放到显示框」。"""
    from PySide6.QtGui import QImage, QColor
    p = tmp_path / "small.png"
    img = QImage(120, 90, QImage.Format_RGB888)
    img.fill(QColor(200, 60, 60))
    assert img.save(str(p))
    return p


def test_适应窗口不放大小图(qapp, tmp_path):
    v = Viewer([_small_pic(tmp_path)], 0)
    v.resize(1000, 700)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    v._set_fit(FIT_WINDOW)
    assert v._effective_scale() == 1.0, "原版行为：小图保持原尺寸"
    v.close()


def test_缩放到显示框会放大小图(qapp, tmp_path):
    v = Viewer([_small_pic(tmp_path)], 0)
    v.resize(1000, 700)
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    v._set_fit(FIT_FILL)
    s = v._effective_scale()
    assert s > 1.0, "小图必须放大"
    # 贴住短边：120x90 放进 1000x700 → 受高度限制
    assert s == pytest.approx(min(v.width() / 120, v.height() / 90))
    assert int(120 * s) <= v.width() and int(90 * s) <= v.height(), "不能超出显示框"
    v.close()


def test_缩放到显示框保持长宽比(qapp, tmp_path):
    v = Viewer([_small_pic(tmp_path)], 0)
    v.resize(400, 900)          # 竖长窗口，和图的横长比例相反
    v.show()
    pump(qapp, 4000, lambda: v._image is not None)
    v._set_fit(FIT_FILL)
    s = v._effective_scale()
    assert s == pytest.approx(v.width() / 120), "该受宽度限制"
    assert int(90 * s) < v.height(), "高度方向留白，不拉伸"
    v.close()


def test_大图时两种模式一致(qapp, viewer):
    """图比窗口大时，适应窗口和缩放到显示框算出来是同一个值。"""
    viewer._set_fit(FIT_WINDOW)
    a = viewer._effective_scale()
    viewer._set_fit(FIT_FILL)
    assert viewer._effective_scale() == pytest.approx(a)
    assert a < 1.0, "夹具图应该比窗口大，否则这条测试没意义"


def test_缩放模式跨图保持(qapp, viewer):
    """幻灯放映时选了缩放到显示框，每张都该铺满，不能翻一张就退回适应窗口。"""
    viewer._set_fit(FIT_FILL)
    viewer.next_image()
    pump(qapp, 4000, lambda: viewer._image is not None)
    assert viewer._fit_mode == FIT_FILL


def test_手动缩放后翻页回到选定模式(qapp, viewer):
    viewer._set_fit(FIT_FILL)
    viewer.zoom_by(+1)                 # 进入 FIT_FREE
    assert viewer._fit_mode == FIT_FREE
    viewer.next_image()
    pump(qapp, 4000, lambda: viewer._image is not None)
    assert viewer._fit_mode == FIT_FILL, "该回到缩放到显示框，而不是一律退回适应窗口"


def test_中键在适应模式和1比1之间来回(qapp, viewer):
    """回归：切到 1:1 时 _base_fit 也会变成 1:1，直接读它就再也切不回来。"""
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent, QPointF

    def middle_click():
        ev = QMouseEvent(QEvent.MouseButtonRelease, QPointF(10, 10), QPointF(10, 10),
                         Qt.MiddleButton, Qt.MiddleButton, Qt.NoModifier)
        viewer.mouseReleaseEvent(ev)

    viewer._set_fit(FIT_WINDOW)
    middle_click()
    assert viewer._fit_mode == FIT_ONE_TO_ONE
    middle_click()
    assert viewer._fit_mode == FIT_WINDOW, "该回到你选的适应模式"
    middle_click()
    assert viewer._fit_mode == FIT_ONE_TO_ONE, "来回切必须一直有效"
