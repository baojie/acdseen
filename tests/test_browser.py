"""Browser: model, on-demand thumbnail loading, file operations, sorting."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QMessageBox

from acdseen import config, i18n
from acdseen.i18n import tr
from acdseen.browser import Browser
from acdseen.util import list_images
from conftest import pump


@pytest.fixture
def browser(qapp, workdir):
    b = Browser(workdir)
    b.resize(1100, 720)
    b.show()
    pump(qapp, 4000)
    yield b
    b.close()
    pump(qapp, 300)


def image_index(browser, n: int):
    """The QModelIndex of the nth image in the view -- row numbers shift by 1 when there's a ".." row."""
    m = browser._model
    return m.index(m.index_of(m.paths()[n]), 0)


def select_image(browser, n: int) -> None:
    browser._view.setCurrentIndex(image_index(browser, n))


@pytest.fixture
def yes(monkeypatch):
    """Make the confirmation dialog return Yes."""
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))


def test_lists_images_in_directory(browser, workdir):
    assert browser._model.image_count() == len(list_images(workdir))


def test_visible_items_get_thumbnails(qapp, browser):
    """Only visible items are required -- invisible ones shouldn't be decoded for nothing."""
    assert pump(qapp, 15000, lambda: len(browser._model._thumbs) > 0)
    thumbs = [t for t in browser._model._thumbs.values() if t is not None]
    assert thumbs


def test_broken_file_shows_placeholder_not_crash(qapp, browser, workdir):
    broken = workdir / "broken.jpg"
    browser._model._requested.add(broken)
    browser._loader.request(broken, browser._model.thumb_size())
    assert pump(qapp, 8000, lambda: broken in browser._model._thumbs)
    assert browser._model._thumbs[broken] is not None   # broken icon, not None


def test_changing_sort_changes_order(browser):
    by_name = [p.name for p in browser._model.paths()]
    browser._set_sort(config.SORT_SIZE)
    by_size = [p.name for p in browser._model.paths()]
    assert sorted(by_name) == sorted(by_size)
    assert by_name != by_size


def test_reverse_order(browser):
    forward = [p.name for p in browser._model.paths()]
    browser._sort_rev_act.setChecked(True)
    browser._toggle_sort_order()
    assert [p.name for p in browser._model.paths()] == forward[::-1]


def test_thumbnail_size_steps(browser):
    start = browser._model.thumb_size()
    browser._step_thumb(+1)
    assert browser._model.thumb_size() > start
    browser._step_thumb(-1)
    assert browser._model.thumb_size() == start


def test_thumbnail_size_stays_in_range(browser):
    for _ in range(20):
        browser._step_thumb(+1)
    assert browser._model.thumb_size() == config.THUMB_SIZES[-1]
    for _ in range(20):
        browser._step_thumb(-1)
    assert browser._model.thumb_size() == config.THUMB_SIZES[0]


def test_toggles_tree_visibility(browser):
    """F9 only toggles the directory tree; the preview pane stays put."""
    assert browser._left_splitter.sizes()[0] > 0
    browser._toggle_tree()
    assert browser._left_splitter.sizes()[0] == 0
    browser._toggle_tree()
    assert browser._left_splitter.sizes()[0] > 0


def test_clicking_symlinked_dir_does_not_jump_to_real_path(qapp, tmp_path, pics):
    """Regression: set_directory used resolve(), so clicking a symlinked directory
    jumped to the real path and the selected tree row hopped away from the clicked line."""
    import os
    real = tmp_path / "real" / "photos"
    real.mkdir(parents=True)
    (real / "a.png").write_bytes((pics / "IMG_001.png").read_bytes())
    link = tmp_path / "link_to_photos"
    os.symlink(real, link)

    b = Browser(tmp_path)
    b.resize(900, 600)
    b.show()
    pump(qapp, 1500)

    fs, tree = b._fs, b._tree
    root = fs.index(str(tmp_path))
    fs.fetchMore(root)
    pump(qapp, 1000)

    idx = fs.index(str(link))
    assert idx.isValid(), "the fixture never created the symlink, so this test proves nothing"
    tree.setCurrentIndex(idx)          # equivalent to the user clicking this row
    pump(qapp, 1000)

    assert b._dir == link, "the current directory should stay on the symlink itself"
    assert fs.filePath(tree.currentIndex()) == str(link), "the tree must not jump to real/photos"
    assert [p.name for p in b._model.paths()] == ["a.png"], "the contents must still be listed normally"
    b.close()
    pump(qapp, 300)


def test_syncing_tree_selection_does_not_recurse(qapp, browser, tmp_path):
    """setCurrentIndex inside set_directory must not re-trigger _on_tree_changed --
    currentChanged is wired to the selectionModel, so intercepting QTreeView signals can't stop it."""
    calls = []
    orig = browser.set_directory
    browser.set_directory = lambda d: (calls.append(d), orig(d))[1]
    idx = browser._fs.index(str(tmp_path))
    if idx.isValid():
        browser._tree.setCurrentIndex(idx)
        pump(qapp, 500)
        assert len(calls) == 1, f"set_directory re-entered: {calls}"
    browser.set_directory = orig


def test_slideshow_starts_at_given_image(qapp, browser):
    browser._start_slideshow(2)
    pump(qapp, 500)
    v = browser._viewer
    assert v is not None, "it should have switched to the viewer page"
    assert v.current == browser._model.paths()[2], "it should start at the 3rd image, not the 1st"
    assert v._slideshow.isActive(), "the slideshow never started"
    browser._on_exit_view(None)
    pump(qapp, 300)


def test_slideshow_start_index_is_clamped(qapp, browser):
    n = browser._model.image_count()
    browser._start_slideshow(n + 99)
    pump(qapp, 500)
    assert browser._viewer.current == browser._model.paths()[n - 1]
    browser._on_exit_view(None)
    pump(qapp, 300)


def test_menu_slideshow_still_starts_at_first(qapp, browser):
    """triggered passes in a checked boolean; wiring it straight to _start_slideshow would treat it as an index."""
    act = next(a for a in browser.actions() if a.text() == tr("action.slideshow_first"))
    act.trigger()
    pump(qapp, 500)
    assert browser._viewer.current == browser._model.paths()[0]
    browser._on_exit_view(None)
    pump(qapp, 300)


def test_context_menu_has_slideshow(qapp, browser):
    """Build the menu but don't exec -- exec is modal, and once it pops up in a test it never returns."""
    rect = browser._view.visualRect(image_index(browser, 0))
    m = browser._build_file_menu(rect.center())
    acts = [a.text() for a in m.actions()]
    assert tr("ctx.slideshow") in acts
    assert acts.index(tr("ctx.slideshow")) == acts.index(tr("ctx.view")) + 1, "it must sit directly under View"
    assert m.actions()[acts.index(tr("ctx.slideshow"))].isEnabled()
    m.deleteLater()


def test_slideshow_disabled_on_empty_area(qapp, browser):
    from PySide6.QtCore import QPoint
    browser._view.clearSelection()
    browser._view.setCurrentIndex(browser._model.index(-1, 0))
    m = browser._build_file_menu(QPoint(5, 100000))   # blank area below the list
    acts = [a.text() for a in m.actions()]
    assert not m.actions()[acts.index(tr("ctx.slideshow"))].isEnabled()
    m.deleteLater()


def test_toggles_preview_pane(browser):
    """Simulate a menu click: Qt toggles checked first, then emits triggered which calls _toggle_preview."""
    assert browser._preview.isVisible()
    browser._preview_act.setChecked(False)
    browser._toggle_preview()
    assert not browser._preview.isVisible()
    browser._preview_act.setChecked(True)
    browser._toggle_preview()
    assert browser._preview.isVisible()


# ------------------------------------------------------------------ file operations
def test_rename(qapp, browser, workdir):
    from PySide6.QtWidgets import QInputDialog
    target = browser._model.paths()[0]
    select_image(browser, 0)

    import acdseen.browser as B
    orig = QInputDialog.getText
    QInputDialog.getText = staticmethod(lambda *a, **k: ("renamed" + target.suffix, True))
    try:
        browser._rename()
    finally:
        QInputDialog.getText = orig

    assert not target.exists()
    assert (workdir / ("renamed" + target.suffix)).exists()


def test_rename_to_existing_name_is_rejected(qapp, browser, workdir, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    paths = browser._model.paths()
    first, second = paths[0], paths[1]
    select_image(browser, 0)

    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warned.append(a)))
    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (second.name, True)))
    browser._rename()

    assert warned, "overwriting a file of the same name must be blocked"
    assert first.exists() and second.exists()


def test_delete_selected(qapp, browser, yes):
    target = browser._model.paths()[0]
    select_image(browser, 0)
    browser._delete()
    pump(qapp, 300)
    assert not target.exists()
    assert target not in browser._model.paths()


def test_delete_multiple(qapp, browser, yes):
    sm = browser._view.selectionModel()
    targets = browser._model.paths()[:3]
    for r in range(3):
        sm.select(browser._model.index(r + browser._model._offset(), 0),
                  QItemSelectionModel.Select)
    browser._delete()
    pump(qapp, 300)
    assert not any(t.exists() for t in targets)


def test_copy_paste_to_another_directory(qapp, browser, tmp_path):
    src = browser._model.paths()[0]
    select_image(browser, 0)
    browser._copy()
    assert browser._clipboard[0] == "copy"

    dest = tmp_path / "dest"
    dest.mkdir()
    browser._do_transfer([src], dest, move=False)
    assert (dest / src.name).exists()
    assert src.exists(), "copying must not touch the source file"


def test_cut_is_move(qapp, browser, tmp_path):
    src = browser._model.paths()[0]
    dest = tmp_path / "moved"
    dest.mkdir()
    browser._do_transfer([src], dest, move=True)
    assert (dest / src.name).exists()
    assert not src.exists()


def test_name_conflict_renames_instead_of_overwriting(qapp, browser, tmp_path):
    src = browser._model.paths()[0]
    dest = tmp_path / "clash"
    dest.mkdir()
    (dest / src.name).write_bytes(b"existing content")

    browser._do_transfer([src], dest, move=False)
    assert (dest / src.name).read_bytes() == b"existing content", "the existing file was overwritten"
    assert (dest / f"{src.stem} (2){src.suffix}").exists()


def test_paste_into_same_directory_does_not_self_overwrite(qapp, browser, workdir):
    src = browser._model.paths()[0]
    before = src.read_bytes()
    browser._clipboard = ("copy", [src])
    browser._paste()
    pump(qapp, 300)
    assert src.read_bytes() == before


# ------------------------------------------------------------------ viewer mode
def test_viewing_opens_no_new_window(qapp, browser):
    """Core requirement: viewing is a page switch inside the same window, not a popup."""
    from PySide6.QtWidgets import QApplication

    def visible_windows():
        return [w for w in QApplication.topLevelWidgets()
                if w.isWindow() and w.isVisible()]

    before = len(visible_windows())
    v = browser._open_viewer(0)
    pump(qapp, 1000)
    assert len(visible_windows()) == before, "a new window was opened"
    assert browser._stack.currentWidget() is v
    assert not v.isWindow(), "the viewer page must be a child widget, not its own window"


def test_entering_and_leaving_view_switches_pages(qapp, browser):
    assert not browser.is_viewing()
    v = browser._open_viewer(0)
    assert browser.is_viewing()
    assert browser._stack.currentWidget() is v

    browser._on_exit_view(None)
    pump(qapp, 500)
    assert not browser.is_viewing()
    assert browser._stack.currentWidget() is browser._splitter


def test_status_bar_hidden_while_viewing(qapp, browser):
    assert browser._status.isVisible()
    browser._open_viewer(0)
    pump(qapp, 300)
    assert not browser._status.isVisible(), "while viewing, information goes to the OSD; the status bar is redundant"
    browser._on_exit_view(None)
    pump(qapp, 300)
    assert browser._status.isVisible()


def test_browser_shortcuts_disabled_while_viewing(qapp, browser):
    """WindowShortcut actions like Del / Enter / F5 fire before Viewer.keyPressEvent."""
    assert all(a.isEnabled() for a in browser._browse_actions)
    browser._open_viewer(0)
    assert all(not a.isEnabled() for a in browser._browse_actions)
    browser._on_exit_view(None)
    pump(qapp, 300)
    assert all(a.isEnabled() for a in browser._browse_actions)


def test_space_paging_not_stolen_while_viewing(qapp, browser):
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    v = browser._open_viewer(0)
    pump(qapp, 4000, lambda: v._image is not None)
    QApplication.sendEvent(v, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Space, Qt.NoModifier))
    pump(qapp, 1500)
    assert v._index == 1, "the browser shortcut swallowed the space key"


def test_menu_bar_hidden_in_fullscreen(qapp, browser):
    v = browser._open_viewer(0)
    pump(qapp, 500)
    v.toggle_fullscreen()
    pump(qapp, 800)
    assert browser.isFullScreen()
    assert not browser.menuBar().isVisible(), "in full screen nothing but the image should remain"

    v.toggle_fullscreen()
    pump(qapp, 800)
    assert browser.menuBar().isVisible()


def test_leaving_view_also_leaves_fullscreen(qapp, browser):
    v = browser._open_viewer(0)
    pump(qapp, 500)
    v.toggle_fullscreen()
    pump(qapp, 800)
    browser._on_exit_view(None)
    pump(qapp, 800)
    assert not browser.isFullScreen(), "back in the browser but still full screen, with no menu bar"
    assert browser.menuBar().isVisible()


def test_thumbnail_pool_paused_while_viewing(qapp, browser):
    assert not browser._loader._paused
    browser._open_viewer(0)
    assert browser._loader._paused, "thumbnails are still competing for CPU while viewing"
    browser._on_exit_view(None)
    pump(qapp, 500)
    assert not browser._loader._paused, "thumbnail loading never resumed after leaving the viewer"


def test_viewer_delete_syncs_to_list(qapp, browser, yes):
    v = browser._open_viewer(0)
    pump(qapp, 4000, lambda: v._image is not None)
    doomed = v.current
    v.delete_current()
    pump(qapp, 500)
    assert doomed not in browser._model.paths()
    browser._on_exit_view(None)


def test_selection_returns_to_current_image_after_view(qapp, browser):
    v = browser._open_viewer(2)
    pump(qapp, 4000, lambda: v._image is not None)
    expected = v.current
    v.exit_view.emit(v.current)      # equivalent to pressing Esc
    pump(qapp, 500)
    assert browser._model.path_at(browser._view.currentIndex()) == expected


def test_reopening_viewer_leaks_no_pages(qapp, browser):
    n = browser._stack.count()
    for i in range(3):
        browser._open_viewer(i)
        pump(qapp, 300)
    browser._on_exit_view(None)
    pump(qapp, 500)
    assert browser._stack.count() == n, "the old viewer page was never torn down"


def test_empty_directory_does_not_crash(qapp, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    b = Browser(empty)
    b.show()
    pump(qapp, 500)
    assert b._model.image_count() == 0
    b._update_status()
    b.close()


# ------------------------------------------------------------------ preview pane
def test_selection_appears_in_preview_pane(qapp, browser):
    # Note: don't use paths()[0]; under natural sort broken.jpg comes before
    # IMG_xxx. That's the fixture's deliberately corrupt file, which never
    # decodes. Use an image that actually can be decoded.
    target = next(p for p in browser._model.paths() if p.name != "broken.jpg")
    browser._view.setCurrentIndex(browser._model.index(browser._model.index_of(target), 0))
    assert browser._preview._path == target, "the selection should reach the preview"
    assert pump(qapp, 8000, lambda: browser._preview._img is not None)
    assert not browser._preview._error


def test_preview_follows_selection(qapp, browser):
    first, second = browser._model.paths()[0], browser._model.paths()[1]
    select_image(browser, 1)
    assert browser._preview._path == second
    pump(qapp, 8000, lambda: browser._preview._img is not None)
    select_image(browser, 0)
    assert browser._preview._path == first


def test_broken_file_preview_marks_error_not_crash(qapp, browser, workdir):
    browser._preview.show_path(workdir / "broken.jpg")
    assert pump(qapp, 6000, lambda: browser._preview._error)
    browser._preview.repaint()          # error state must be drawable too


def test_preview_cleared_on_empty_directory(qapp, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    b = Browser(empty)
    b.show()
    pump(qapp, 500)
    assert b._preview._path is None
    assert b._preview.isVisible(), "the pane itself stays; it just shows a placeholder hint"
    b.close()


def test_preview_pauses_while_viewing_and_resumes(qapp, browser):
    browser._open_viewer(0)
    pump(qapp, 500)
    pv = browser._preview
    assert pv._paused, "the preview should be paused while viewing"
    assert pv._img is None, "pausing must void the in-flight decode"
    # Key regression: switching pages triggers resize; while paused, the debounce timer must not pull it back up
    assert not pv._resize_timer.isActive()
    assert pump(qapp, 2000, lambda: pv._pool.activeThreadCount() == 0), \
        "no preview decode thread should still be running while viewing"

    browser._on_exit_view(None)
    pump(qapp, 500)
    assert not pv._paused
    assert pv._path == browser._current_path(), "after leaving the viewer the preview returns to the selection"
    assert pump(qapp, 8000, lambda: pv._img is not None or pv._error), "decoding should resume after leaving"


# ------------------------------------------------------------------ view mode
def test_thumbnail_mode_is_default(browser):
    from PySide6.QtWidgets import QListView
    from acdseen.thumbmodel import ThumbDelegate
    assert browser._view_mode == config.VIEW_THUMBS
    assert browser._view is browser._icon_view
    assert browser._view.viewMode() == QListView.IconMode
    assert isinstance(browser._view.itemDelegate(), ThumbDelegate)


def test_switch_to_list_mode(qapp, browser):
    from PySide6.QtWidgets import QTreeView
    browser._toggle_view_mode()
    pump(qapp, 500)
    assert browser._view_mode == config.VIEW_LIST
    assert isinstance(browser._view, QTreeView)
    assert browser._view is browser._list_view
    assert browser._model.thumb_size() == config.LIST_THUMB_SIZE
    browser._view.repaint()          # list mode must be drawable


def test_switching_views_keeps_selection(qapp, browser):
    select_image(browser, 2)
    keep = browser._current_path()
    browser._toggle_view_mode()
    pump(qapp, 500)
    assert browser._current_path() == keep, "set_thumb_size resets the model, so the selection has to be restored"
    browser._toggle_view_mode()
    pump(qapp, 500)
    assert browser._current_path() == keep


def test_list_mode_does_not_overwrite_thumbnail_edge(qapp, browser):
    """Regression: list mode shrinks the model size to 40; that value must not be persisted as the user's chosen thumbnail size."""
    browser._thumb_edge = 160
    browser._set_view_mode(config.VIEW_THUMBS)
    browser._model.set_thumb_size(160)
    browser._toggle_view_mode()      # -> list
    pump(qapp, 300)
    assert browser._model.thumb_size() == config.LIST_THUMB_SIZE
    assert browser._thumb_edge == 160, "list mode swallowed the thumbnail edge the user picked"
    browser._toggle_view_mode()      # -> thumbnails
    pump(qapp, 300)
    assert browser._model.thumb_size() == 160, "switching back must restore the user's edge length"


def test_resizing_thumbnails_in_list_mode_returns_to_grid(qapp, browser):
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._step_thumb(+1)
    assert browser._view_mode == config.VIEW_THUMBS


def test_all_list_columns_have_content(browser):
    from PySide6.QtCore import Qt
    from acdseen.thumbmodel import (COL_DIMS, COL_MTIME, COL_NAME, COL_SIZE,
                                    COL_TYPE, COLUMNS)
    row = browser._model.index_of(
        next(p for p in browser._model.paths() if p.name != "broken.jpg"))
    cell = lambda c: browser._model.data(browser._model.index(row, c), Qt.DisplayRole)
    assert browser._model.columnCount() == len(COLUMNS)
    assert cell(COL_NAME)
    assert "×" in cell(COL_DIMS)
    assert cell(COL_SIZE)
    assert cell(COL_TYPE)
    assert cell(COL_MTIME)


def test_header_has_titles(browser):
    from PySide6.QtCore import Qt
    from acdseen.thumbmodel import COLUMNS
    titles = [browser._model.headerData(i, Qt.Horizontal)
              for i in range(browser._model.columnCount())]
    # The first column of COLUMNS is an i18n id; the title is the translated text
    assert titles == [i18n.tr(t) for t, _k, _w in COLUMNS]
    hdr = browser._list_view.header()
    assert hdr.sectionsClickable(), "the header must be clickable"


def test_view_mode_persists(qapp, workdir):
    b = Browser(workdir)
    b.show(); pump(qapp, 1500)
    b._set_view_mode(config.VIEW_LIST)
    b.close(); pump(qapp, 300)

    b2 = Browser(workdir)
    b2.show(); pump(qapp, 1500)
    assert b2._view_mode == config.VIEW_LIST, "the view mode was never stored in QSettings"
    b2.close(); pump(qapp, 300)


# ------------------------------------------------------------------ sorting
def test_sort_menu_covers_all_keys(browser):
    assert {k for _, k in browser._sort_acts} == set(config.SORT_NAMES)


def test_changing_sort_reorders_list(qapp, browser):
    browser._set_sort(config.SORT_SIZE)
    pump(qapp, 500)
    sizes = [p.stat().st_size for p in browser._model.paths()]
    assert sizes == sorted(sizes)
    browser._set_sort(config.SORT_NAME)
    pump(qapp, 500)
    names = [p.name for p in browser._model.paths()]
    assert names == [p.name for p in list_images(browser._dir, config.SORT_NAME)]


def test_random_sort_does_not_reshuffle_on_refresh(qapp, browser):
    """Deleting an image triggers refresh(); the whole grid must not be re-shuffled then."""
    browser._set_sort(config.SORT_RANDOM)
    pump(qapp, 500)
    before = list(browser._model.paths())
    browser.refresh()
    pump(qapp, 500)
    assert browser._model.paths() == before, "the seed did not hold: refresh reshuffled the order"


def test_clicking_random_again_reshuffles(qapp, browser):
    browser._set_sort(config.SORT_RANDOM)
    pump(qapp, 300)
    first, seed = list(browser._model.paths()), browser._sort_seed
    browser._set_sort(config.SORT_RANDOM)
    pump(qapp, 300)
    assert browser._sort_seed != seed, "clicking Random again should deal a new hand"
    assert sorted(browser._model.paths()) == sorted(first), "not a single image may go missing"


# ------------------------------------------------------------------ header sorting
def test_clicking_header_sorts_by_column(qapp, browser):
    from acdseen.thumbmodel import COL_SIZE
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._on_header_clicked(COL_SIZE)
    pump(qapp, 500)
    assert browser._sort_key == config.SORT_SIZE
    sizes = [p.stat().st_size for p in browser._model.paths()]
    assert sizes == sorted(sizes)


def test_clicking_same_column_reverses(qapp, browser):
    from acdseen.thumbmodel import COL_SIZE
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._on_header_clicked(COL_SIZE)
    pump(qapp, 400)
    up = list(browser._model.paths())
    assert not browser._sort_reverse
    browser._on_header_clicked(COL_SIZE)
    pump(qapp, 400)
    assert browser._sort_reverse
    assert browser._model.paths() == list(reversed(up))


def test_clicking_other_column_returns_to_ascending(qapp, browser):
    from acdseen.thumbmodel import COL_NAME, COL_SIZE
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._on_header_clicked(COL_SIZE)
    browser._on_header_clicked(COL_SIZE)      # switch to descending
    pump(qapp, 400)
    assert browser._sort_reverse
    browser._on_header_clicked(COL_NAME)      # switch to another column
    pump(qapp, 400)
    assert browser._sort_key == config.SORT_NAME
    assert not browser._sort_reverse, "switching columns should return to ascending"
    assert browser._sort_rev_act.isChecked() is False, "the menu's Reverse entry must follow"


def test_header_arrow_follows_menu_sort(qapp, browser):
    from PySide6.QtCore import Qt
    from acdseen.thumbmodel import COL_SIZE
    hdr = browser._list_view.header()
    browser._set_sort(config.SORT_SIZE)
    pump(qapp, 300)
    assert hdr.isSortIndicatorShown()
    assert hdr.sortIndicatorSection() == COL_SIZE
    assert hdr.sortIndicatorOrder() == Qt.AscendingOrder
    browser._sort_rev_act.setChecked(True)
    browser._toggle_sort_order()
    pump(qapp, 300)
    assert hdr.sortIndicatorOrder() == Qt.DescendingOrder


def test_arrow_hidden_for_random_sort(qapp, browser):
    """Random doesn't correspond to any column; forcing one would mislead."""
    hdr = browser._list_view.header()
    browser._set_sort(config.SORT_RANDOM)
    pump(qapp, 300)
    assert not hdr.isSortIndicatorShown()


def test_list_mode_multiselect_counts_once(qapp, browser):
    """A QTreeView row has 5 indexes; without dedup, one file gets counted 5 times."""
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    browser._view.selectAll()
    pump(qapp, 300)
    n = browser._model.image_count()
    # Select-all also selects the ".." row, so the index count uses rowCount
    assert len(browser._view.selectedIndexes()) == browser._model.rowCount() * 5
    assert len(browser._selected_paths()) == n, '".." is not an image and must stay out of the selection'
    assert tr("status.selected", n) in browser._status_left.text()


def test_both_views_share_selection(qapp, browser):
    select_image(browser, 2)
    keep = browser._current_path()
    assert browser._icon_view.selectionModel() is browser._list_view.selectionModel()
    browser._set_view_mode(config.VIEW_LIST)
    pump(qapp, 300)
    assert browser._current_path() == keep


# ------------------------------------------------------------------ parent directory row
def test_first_row_is_parent_directory(browser):
    m = browser._model
    idx = m.index(0, 0)
    assert m.is_parent_row(idx)
    assert m.data(idx, Qt.DisplayRole) == ".."
    assert m.parent_dir() == browser._dir.parent
    assert m.rowCount() == m.image_count() + 1


def test_parent_row_is_not_an_image(browser):
    """It must not leak into the selection, preview, or file operations -- those all rely on path_at returning None."""
    m = browser._model
    idx = m.index(0, 0)
    assert m.path_at(idx) is None
    assert m.image_index(idx) == -1
    browser._view.setCurrentIndex(idx)
    assert browser._current_path() is None
    assert browser._selected_paths() == [], '".." must never count as a selected file'


def test_double_click_parent_row_goes_up(qapp, browser, workdir):
    parent = workdir.parent
    browser._open_index(browser._model.index(0, 0))
    pump(qapp, 800)
    assert browser._dir == parent


def test_root_has_no_parent_row(qapp):
    from pathlib import Path
    b = Browser(Path("/"))
    b.show(); pump(qapp, 1200)
    assert b._model.parent_dir() is None
    assert not b._model.is_parent_row(b._model.index(0, 0))
    b.close(); pump(qapp, 300)


def test_after_directory_change_first_image_is_selected(qapp, browser):
    m = browser._model
    assert m.first_image_row() == 1
    assert not m.is_parent_row(browser._view.currentIndex())
    assert browser._current_path() == m.paths()[0]


def test_status_bar_excludes_parent_row(browser):
    n = len(browser._model.paths())
    assert tr("status.images", n) in browser._status_left.text()


def test_parent_row_context_menu_only_goes_up(browser):
    m = browser._build_file_menu(browser._view.visualRect(
        browser._model.index(0, 0)).center())
    acts = [a.text() for a in m.actions()]
    assert acts == [tr("ctx.parent")]
    m.deleteLater()


# ------------------------------------------------------------------ path bar
def test_path_bar_shows_current_directory(browser, workdir):
    assert browser._path_bar.currentText() == str(workdir)


def test_path_bar_lists_ancestors(browser, workdir):
    items = [browser._path_bar.itemText(i)
             for i in range(browser._path_bar.count())]
    assert items[0] == str(workdir)
    assert items[-1] == "/"
    assert str(workdir.parent) in items


def test_path_bar_accepts_typed_path(qapp, browser, workdir):
    target = workdir.parent
    browser._path_bar.setEditText(str(target))
    browser._on_path_entered()
    pump(qapp, 800)
    assert browser._dir == target


def test_path_bar_change_does_not_recurse(qapp, browser, workdir):
    """Regression: inserting items into the QComboBox triggers activated; without
    blocking the signal, set_directory recurses into set_directory."""
    calls = []
    orig = browser.set_directory
    browser.set_directory = lambda d: (calls.append(d), orig(d))[1]
    browser._on_path_picked(1)          # pick the parent
    pump(qapp, 800)
    assert len(calls) == 1, f"set_directory re-entered: {calls}"
    browser.set_directory = orig
