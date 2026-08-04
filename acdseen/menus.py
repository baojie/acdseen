"""浏览器的菜单：菜单栏、缩略图右键菜单、帮助与关于。

_act() 里那件要紧事：浏览器的快捷键（Del / Enter / F5 / Ctrl+C…）和看图器
的按键撞车，而且 WindowShortcut 上下文会抢在 Viewer.keyPressEvent 之前触发。
所以凡是浏览态才有意义的 QAction 都登记进 _browse_actions，进入看图页时统一
禁用 —— 这一层由 viewhost 负责开关。

切换界面语言时整个菜单要重建：self._menu_actions 收集所有 addAction 到窗口的
action，供 _rebuild_menu 先 removeAction 再重建，免得旧 action 和快捷键残留。

依赖宿主提供：_view _view_mode _sort_key _sort_reverse _preview _model
             以及各操作方法（_open_current / _rename / _delete / …）
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenu, QMessageBox

from . import config, i18n
from .i18n import tr


class MenuMixin:
    # ------------------------------------------------------------- 菜单
    def _build_menu(self) -> None:
        self._browse_actions: list[QAction] = []
        self._menu_actions: list[QAction] = []   # 所有 addAction 到窗口的，重建时清掉
        mb = self.menuBar()

        m_file = mb.addMenu(tr("menu.file"))
        self._act(tr("action.open"), "Return", self._open_current, m_file)
        self._act(tr("action.reveal"), "Ctrl+Shift+O", self._reveal, m_file)
        m_file.addSeparator()
        self._act(tr("action.rename"), "F2", self._rename, m_file)
        self._act(tr("action.delete"), "Del", self._delete, m_file)
        m_file.addSeparator()
        self._act(tr("action.copy"), QKeySequence.Copy, self._copy, m_file)
        self._act(tr("action.cut"), QKeySequence.Cut, self._cut, m_file)
        self._act(tr("action.paste"), QKeySequence.Paste, self._paste, m_file)
        self._act(tr("action.copy_to"), "Ctrl+Shift+C", lambda: self._transfer("copy"), m_file)
        self._act(tr("action.move_to"), "Ctrl+Shift+M", lambda: self._transfer("move"), m_file)
        m_file.addSeparator()
        self._act(tr("action.quit"), "Ctrl+Q", self.close, m_file, browse_only=False)

        m_view = mb.addMenu(tr("menu.view"))
        self._view_acts: list[tuple[QAction, int]] = []
        vgrp = QActionGroup(self); vgrp.setExclusive(True)
        for mode, name in config.VIEW_NAMES.items():
            a = QAction(tr(name), self, checkable=True)
            a.setShortcut(QKeySequence(f"Ctrl+{mode + 1}"))
            a.setChecked(mode == self._view_mode)
            a.triggered.connect(lambda _=False, m=mode: self._set_view_mode(m))
            vgrp.addAction(a); m_view.addAction(a); self.addAction(a)
            self._view_acts.append((a, mode))
            self._browse_actions.append(a)
            self._menu_actions.append(a)
        self._act(tr("action.toggle_view"), "F8", self._toggle_view_mode, m_view)
        m_view.addSeparator()
        self._act(tr("action.select_all"), QKeySequence.SelectAll, lambda: self._view.selectAll(), m_view)
        self._act(tr("action.refresh"), "F5", self.refresh, m_view)
        m_view.addSeparator()
        self._act(tr("action.thumb_larger"), "Ctrl++", lambda: self._step_thumb(+1), m_view)
        self._act(tr("action.thumb_smaller"), "Ctrl+-", lambda: self._step_thumb(-1), m_view)
        m_view.addSeparator()
        self._act(tr("action.toggle_tree"), "F9", self._toggle_tree, m_view)
        self._preview_act = QAction(tr("action.preview_pane"), self, checkable=True)
        self._preview_act.setChecked(True)
        self._preview_act.triggered.connect(self._toggle_preview)
        m_view.addAction(self._preview_act)
        m_view.addSeparator()
        self._win95_act = QAction(tr("action.win95"), self, checkable=True)
        self._win95_act.setChecked(config.DEFAULT_WIN95_LOOK)
        self._win95_act.triggered.connect(self._toggle_win95)
        m_view.addAction(self._win95_act)
        self._act(tr("action.clear_cache"), None, self._clear_cache, m_view)
        m_view.addSeparator()
        self._build_language_menu(m_view)

        m_sort = mb.addMenu(tr("menu.sort"))
        grp = QActionGroup(self); grp.setExclusive(True)
        self._sort_acts: list[tuple[QAction, int]] = []
        for key, name in config.SORT_NAMES.items():
            if key == config.SORT_PIXELS:
                m_sort.addSeparator()        # 以下几项要读文件头，和上面的分开
            a = QAction(tr("sort.by", tr(name)), self, checkable=True)
            a.setChecked(key == self._sort_key)
            if key in config.SORT_NEEDS_DIMS:
                a.setToolTip(tr("sort.tooltip"))
            a.triggered.connect(lambda _=False, k=key: self._set_sort(k))
            grp.addAction(a); m_sort.addAction(a)
            self._sort_acts.append((a, key))
        m_sort.addSeparator()
        self._sort_rev_act = QAction(tr("sort.reverse"), self, checkable=True)
        self._sort_rev_act.triggered.connect(self._toggle_sort_order)
        m_sort.addAction(self._sort_rev_act)

        m_show = mb.addMenu(tr("menu.show"))
        self._act(tr("action.view_selected"), "Return", self._open_current, m_show)
        # 包一层 lambda：triggered 会塞个 checked 布尔进来，直接连会被当成起始张号
        self._act(tr("action.slideshow_first"), "Ctrl+S", lambda: self._start_slideshow(0), m_show)

        m_help = mb.addMenu(tr("menu.help"))
        self._act(tr("action.shortcuts"), "F1", self._show_help, m_help, browse_only=False)
        self._act(tr("action.about"), None, self._show_about, m_help, browse_only=False)

    def _build_language_menu(self, parent: QMenu) -> None:
        """「界面语言」子菜单：每种语言一个单选 action。

        语言名用各自语言的自称，不翻译 —— 语言切换入口必须在自己能
        看懂的语言里也认得出自己。
        """
        m_lang = parent.addMenu(tr("menu.language"))
        grp = QActionGroup(self); grp.setExclusive(True)
        for code, name in i18n.LANG_NAMES.items():
            a = QAction(name, self, checkable=True)
            a.setChecked(i18n.current() == code)
            a.triggered.connect(lambda _=False, c=code: self._set_language(c))
            grp.addAction(a); m_lang.addAction(a)

    def _act(self, text, shortcut, slot, menu, browse_only: bool = True) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut if isinstance(shortcut, QKeySequence) else QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        self.addAction(a)   # 让快捷键在整窗口生效
        self._menu_actions.append(a)
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
        if self._model.is_parent_row(idx):
            m.addAction(tr("ctx.parent"), self._go_parent)
            return m

        m.addAction(tr("ctx.view"), self._open_current)
        # 用图片下标，不是视图行号 —— 有 ".." 行时两者差 1
        row = self._model.image_index(idx)
        act = m.addAction(tr("ctx.slideshow"), lambda: self._start_slideshow(max(0, row)))
        act.setEnabled(row >= 0)
        m.addSeparator()
        m.addAction(tr("ctx.rename"), self._rename)
        m.addAction(tr("ctx.delete"), self._delete)
        m.addSeparator()
        m.addAction(tr("ctx.copy"), self._copy)
        m.addAction(tr("ctx.cut"), self._cut)
        m.addAction(tr("ctx.copy_to"), lambda: self._transfer("copy"))
        m.addAction(tr("ctx.move_to"), lambda: self._transfer("move"))
        return m

    def _show_help(self) -> None:
        QMessageBox.information(self, tr("action.shortcuts"), tr("help.text"))

    def _show_about(self) -> None:
        QMessageBox.about(
            self, tr("about.title", config.APP_NAME), tr("about.text"))
