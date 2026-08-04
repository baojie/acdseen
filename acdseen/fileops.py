"""Browser file operations: rename, delete, copy, cut, paste, copy to, move to.

The original ACDSee 1.2x built these directly into the browser, precisely so you
never had to switch back to a file manager.

Made a mixin rather than a standalone class: these operations read the current
selection, refresh the list, and write to the status bar -- the coupling to
Browser is real, and forcing it apart by "passing a bunch of callbacks" would
only make it more convoluted. The mixin at least moves this chunk out of the
main file, without changing a single character of how self is used.

Expects the host to provide: _current_path() _selected_paths() _update_status() refresh()
                             _model _view _status _dir
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from .i18n import tr


class FileOpsMixin:
    def _rename(self) -> None:
        path = self._current_path()
        if path is None:
            return
        new, ok = QInputDialog.getText(self, tr("rename.title"), tr("rename.prompt"),
                                       QLineEdit.Normal, path.name)
        if not ok or not new.strip() or new == path.name:
            return
        target = path.with_name(new.strip())
        if target.exists():
            QMessageBox.warning(self, tr("rename.title"), tr("err.exists", target.name))
            return
        try:
            path.rename(target)
        except OSError as e:
            QMessageBox.warning(self, tr("err.rename_failed"), str(e))
            return
        self.refresh()
        row = self._model.index_of(target)
        if row >= 0:
            self._view.setCurrentIndex(self._model.index(row, 0))

    def _delete(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        msg = (tr("msg.delete_confirm", paths[0].name) if len(paths) == 1
               else tr("delete.confirm_many", len(paths)))
        if QMessageBox.question(self, tr("action.delete"), msg,
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return
        row = self._view.currentIndex().row()
        failed = []
        for p in paths:
            try:
                p.unlink()
            except OSError as e:
                failed.append(f"{p.name}: {e}")
        self._model.remove_paths(set(paths))
        if self._model.rowCount():
            self._view.setCurrentIndex(
                self._model.index(min(row, self._model.rowCount() - 1), 0))
        if failed:
            QMessageBox.warning(self, tr("err.delete_partial"), "\n".join(failed[:10]))
        self._update_status()

    def _copy(self) -> None:
        paths = self._selected_paths()
        if paths:
            self._clipboard = ("copy", paths)
            self._status.showMessage(tr("status.copied", len(paths)), 2000)

    def _cut(self) -> None:
        paths = self._selected_paths()
        if paths:
            self._clipboard = ("cut", paths)
            self._status.showMessage(tr("status.cut", len(paths)), 2000)

    def _paste(self) -> None:
        if not self._clipboard:
            return
        mode, paths = self._clipboard
        self._do_transfer(paths, self._dir, move=(mode == "cut"))
        if mode == "cut":
            self._clipboard = None
        self.refresh()

    def _transfer(self, mode: str) -> None:
        from PySide6.QtWidgets import QFileDialog
        paths = self._selected_paths()
        if not paths:
            return
        dest = QFileDialog.getExistingDirectory(
            self, tr("action.copy_to") if mode == "copy" else tr("action.move_to"),
            str(self._dir))
        if not dest:
            return
        self._do_transfer(paths, Path(dest), move=(mode == "move"))
        if mode == "move":
            self.refresh()

    def _do_transfer(self, paths: list[Path], dest: Path, move: bool) -> None:
        failed = []
        for p in paths:
            target = dest / p.name
            # The resolve() here is deliberate: deciding whether source and target are the same file must follow symlinks
            if target.resolve() == p.resolve():
                continue
            target = self._unique_name(target)
            try:
                shutil.move(str(p), str(target)) if move else shutil.copy2(str(p), str(target))
            except OSError as e:
                failed.append(f"{p.name}: {e}")
        if failed:
            QMessageBox.warning(self, tr("err.transfer_partial"), "\n".join(failed[:10]))
        else:
            verb = tr("verb.move") if move else tr("verb.copy")
            self._status.showMessage(
                tr("status.transferred", verb=verb, count=len(paths), dest=dest), 3000)

    @staticmethod
    def _unique_name(target: Path) -> Path:
        if not target.exists():
            return target
        stem, suffix = target.stem, target.suffix
        n = 2
        while True:
            cand = target.with_name(f"{stem} ({n}){suffix}")
            if not cand.exists():
                return cand
            n += 1

    def _reveal(self) -> None:
        path = self._current_path() or self._dir
        try:
            subprocess.Popen(["xdg-open", str(path.parent if path.is_file() else path)])
        except OSError:
            pass
