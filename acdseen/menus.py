"""浏览器的菜单：菜单栏、缩略图右键菜单、帮助与关于。

_act() 里那件要紧事：浏览器的快捷键（Del / Enter / F5 / Ctrl+C…）和看图器
的按键撞车，而且 WindowShortcut 上下文会抢在 Viewer.keyPressEvent 之前触发。
所以凡是浏览态才有意义的 QAction 都登记进 _browse_actions，进入看图页时统一
禁用 —— 这一层由 viewhost 负责开关。

依赖宿主提供：_view _view_mode _sort_key _sort_reverse _preview _model
             以及各操作方法（_open_current / _rename / _delete / …）
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenu, QMessageBox

from . import config
from .helptext import HELP_TEXT


class MenuMixin:
    # ------------------------------------------------------------- 菜单
    def _build_menu(self) -> None:
        self._browse_actions: list[QAction] = []
        mb = self.menuBar()

        m_file = mb.addMenu("文件(&F)")
        self._act("打开", "Return", self._open_current, m_file)
        self._act("在文件管理器中显示", "Ctrl+Shift+O", self._reveal, m_file)
        m_file.addSeparator()
        self._act("重命名", "F2", self._rename, m_file)
        self._act("删除", "Del", self._delete, m_file)
        m_file.addSeparator()
        self._act("复制", QKeySequence.Copy, self._copy, m_file)
        self._act("剪切", QKeySequence.Cut, self._cut, m_file)
        self._act("粘贴到当前目录", QKeySequence.Paste, self._paste, m_file)
        self._act("复制到…", "Ctrl+Shift+C", lambda: self._transfer("copy"), m_file)
        self._act("移动到…", "Ctrl+Shift+M", lambda: self._transfer("move"), m_file)
        m_file.addSeparator()
        self._act("退出", "Ctrl+Q", self.close, m_file, browse_only=False)

        m_view = mb.addMenu("查看(&V)")
        self._view_acts: list[tuple[QAction, int]] = []
        vgrp = QActionGroup(self); vgrp.setExclusive(True)
        for mode, name in config.VIEW_NAMES.items():
            a = QAction(name, self, checkable=True)
            a.setShortcut(QKeySequence(f"Ctrl+{mode + 1}"))
            a.setChecked(mode == self._view_mode)
            a.triggered.connect(lambda _=False, m=mode: self._set_view_mode(m))
            vgrp.addAction(a); m_view.addAction(a); self.addAction(a)
            self._view_acts.append((a, mode))
            self._browse_actions.append(a)
        self._act("切换缩略图 / 列表", "F8", self._toggle_view_mode, m_view)
        m_view.addSeparator()
        self._act("全选", QKeySequence.SelectAll, lambda: self._view.selectAll(), m_view)
        self._act("刷新", "F5", self.refresh, m_view)
        m_view.addSeparator()
        self._act("放大缩略图", "Ctrl++", lambda: self._step_thumb(+1), m_view)
        self._act("缩小缩略图", "Ctrl+-", lambda: self._step_thumb(-1), m_view)
        m_view.addSeparator()
        self._act("切换目录树", "F9", self._toggle_tree, m_view)
        self._preview_act = QAction("预览窗格", self, checkable=True)
        self._preview_act.setChecked(True)
        self._preview_act.triggered.connect(self._toggle_preview)
        m_view.addAction(self._preview_act)
        self._act("清空缩略图缓存", None, self._clear_cache, m_view)

        m_sort = mb.addMenu("排序(&S)")
        grp = QActionGroup(self); grp.setExclusive(True)
        self._sort_acts: list[tuple[QAction, int]] = []
        for key, name in config.SORT_NAMES.items():
            if key == config.SORT_PIXELS:
                m_sort.addSeparator()        # 以下几项要读文件头，和上面的分开
            a = QAction(f"按{name}", self, checkable=True)
            a.setChecked(key == self._sort_key)
            if key in config.SORT_NEEDS_DIMS:
                a.setToolTip("需要读取每个文件的图片头，大目录首次会慢一下")
            a.triggered.connect(lambda _=False, k=key: self._set_sort(k))
            grp.addAction(a); m_sort.addAction(a)
            self._sort_acts.append((a, key))
        m_sort.addSeparator()
        self._sort_rev_act = QAction("倒序", self, checkable=True)
        self._sort_rev_act.triggered.connect(self._toggle_sort_order)
        m_sort.addAction(self._sort_rev_act)

        m_show = mb.addMenu("看图(&I)")
        self._act("查看选中图片", "Return", self._open_current, m_show)
        # 包一层 lambda：triggered 会塞个 checked 布尔进来，直接连会被当成起始张号
        self._act("从第一张开始幻灯片", "Ctrl+S", lambda: self._start_slideshow(0), m_show)

        m_help = mb.addMenu("帮助(&H)")
        self._act("快捷键", "F1", self._show_help, m_help, browse_only=False)
        self._act("关于", None, self._show_about, m_help, browse_only=False)

    def _act(self, text, shortcut, slot, menu, browse_only: bool = True) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut if isinstance(shortcut, QKeySequence) else QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        self.addAction(a)   # 让快捷键在整窗口生效
        if browse_only:
            # 这些快捷键（Del / Enter / F5 / Ctrl+C…）和看图器的按键撞车，
            # 且 WindowShortcut 上下文会抢在 Viewer.keyPressEvent 之前触发。
            # 进入看图模式时统一禁用。
            self._browse_actions.append(a)
        return a

    def _file_context_menu(self, pos) -> None:
        m = self._build_file_menu(pos)
        m.exec(self._view.viewport().mapToGlobal(pos))

    def _build_file_menu(self, pos) -> QMenu:
        """构造缩略图右键菜单。和 exec 分开，测试才能不弹模态窗就检查内容。"""
        # 作用于右键点中的那一项。Qt 右键也会移动当前项，两者通常一致，
        # 但点在空白处时 indexAt 无效，那就退回当前项。
        idx = self._view.indexAt(pos)
        if not idx.isValid():
            idx = self._view.currentIndex()

        m = QMenu(self)
        m.addAction("查看\tEnter", self._open_current)
        row = idx.row()
        act = m.addAction("幻灯演示", lambda: self._start_slideshow(row))
        act.setEnabled(idx.isValid())
        m.addSeparator()
        m.addAction("重命名\tF2", self._rename)
        m.addAction("删除\tDel", self._delete)
        m.addSeparator()
        m.addAction("复制\tCtrl+C", self._copy)
        m.addAction("剪切\tCtrl+X", self._cut)
        m.addAction("复制到…", lambda: self._transfer("copy"))
        m.addAction("移动到…", lambda: self._transfer("move"))
        return m

    def _show_help(self) -> None:
        QMessageBox.information(self, "快捷键", HELP_TEXT)

    def _show_about(self) -> None:
        QMessageBox.about(
            self, f"关于 {config.APP_NAME}",
            f"<b>{config.APP_NAME}</b><br><br>"
            "1996 年 ACDSee 1.2x 的复刻：一个浏览器 + 一个看图器，<br>"
            "没有数据库，没有编辑器，没有云。<br><br>"
            "只求打开得快、翻页不卡、手不离键盘。")
