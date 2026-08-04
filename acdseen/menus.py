"""The browser's menus: the menu bar, the thumbnail context menu, and help/about.

The critical thing in _act(): the browser's shortcuts (Del / Enter / F5 / Ctrl+C ...)
collide with the viewer's key handling, and the WindowShortcut context fires before
Viewer.keyPressEvent. So every QAction that only makes sense in browse mode is
registered in _browse_actions and disabled uniformly when entering the viewer page
-- that switch is handled by viewhost.

Switching the UI language rebuilds the whole menu: self._menu_actions collects every
action added to the window, so _rebuild_menu can removeAction them first and then
rebuild, preventing stale actions and shortcuts from lingering.

Expects the host to provide: _view _view_mode _sort_key _sort_reverse _preview _model
                             and the action methods (_open_current / _rename / _delete / ...)
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenu, QMessageBox

from . import config, i18n
from .i18n import tr


class MenuMixin:
    # ------------------------------------------------------------- Menus
    def _build_menu(self) -> None:
        self._browse_actions: list[QAction] = []
        self._menu_actions: list[QAction] = []   # all actions added to the window, cleared on rebuild
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
                m_sort.addSeparator()        # the following entries need to read file headers, keep them apart from the ones above
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
        # Wrap in a lambda: triggered passes a checked bool in, and connecting directly would treat it as the start index
        self._act(tr("action.slideshow_first"), "Ctrl+S", lambda: self._start_slideshow(0), m_show)

        m_help = mb.addMenu(tr("menu.help"))
        self._act(tr("action.shortcuts"), "F1", self._show_help, m_help, browse_only=False)
        self._act(tr("action.about"), None, self._show_about, m_help, browse_only=False)

    def _build_language_menu(self, parent: QMenu) -> None:
        """The "interface language" submenu: one radio action per language.

        Language names use each language's own self-name, not a translation --
        the language-switch entry point must be recognizable in a language the
        user can already read.
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
        self.addAction(a)   # make the shortcut work across the whole window
        self._menu_actions.append(a)
        if browse_only:
            # These shortcuts (Del / Enter / F5 / Ctrl+C ...) collide with the
            # viewer's key handling, and the WindowShortcut context fires before
            # Viewer.keyPressEvent. Disable them uniformly when entering viewer mode.
            self._browse_actions.append(a)
        return a

    def _file_context_menu(self, pos) -> None:
        m = self._build_file_menu(pos)
        m.exec(self._view.viewport().mapToGlobal(pos))

    def _build_file_menu(self, pos) -> QMenu:
        """Build the thumbnail context menu. Kept separate from exec so tests can inspect it without popping a modal window."""
        # Operate on the item that was right-clicked. Qt's right-click also moves
        # the current item, so the two usually agree, but indexAt is invalid when
        # clicking empty space -- fall back to the current item.
        idx = self._view.indexAt(pos)
        if not idx.isValid():
            idx = self._view.currentIndex()

        m = QMenu(self)
        if self._model.is_parent_row(idx):
            m.addAction(tr("ctx.parent"), self._go_parent)
            return m

        m.addAction(tr("ctx.view"), self._open_current)
        # Use the image index, not the view row number -- they differ by 1 when a ".." row is present
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
