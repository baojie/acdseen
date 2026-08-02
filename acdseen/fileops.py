"""浏览器的文件操作：重命名、删除、复制、剪切、粘贴、复制到、移动到。

原版 ACDSee 1.2x 把这些直接内建在浏览器里，就是为了不用切回文件管理器。

做成 mixin 而不是独立类：这些操作要读当前选中项、要刷新列表、要往状态栏
写消息，和 Browser 的耦合是真实存在的，硬拆成"传一堆回调进去"只会更绕。
mixin 至少把这一坨从主文件里挪出去，且 self 的用法一个字都不用改。

依赖宿主提供：_current_path() _selected_paths() _update_status() refresh()
             _model _view _status _dir
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox


class FileOpsMixin:
    def _rename(self) -> None:
        path = self._current_path()
        if path is None:
            return
        new, ok = QInputDialog.getText(self, "重命名", "新名称：",
                                       QLineEdit.Normal, path.name)
        if not ok or not new.strip() or new == path.name:
            return
        target = path.with_name(new.strip())
        if target.exists():
            QMessageBox.warning(self, "重命名", f"{target.name} 已存在。")
            return
        try:
            path.rename(target)
        except OSError as e:
            QMessageBox.warning(self, "重命名失败", str(e))
            return
        self.refresh()
        row = self._model.index_of(target)
        if row >= 0:
            self._view.setCurrentIndex(self._model.index(row, 0))

    def _delete(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        msg = f"删除 {paths[0].name}？" if len(paths) == 1 else f"删除选中的 {len(paths)} 个文件？"
        if QMessageBox.question(self, "删除", msg,
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
            QMessageBox.warning(self, "部分删除失败", "\n".join(failed[:10]))
        self._update_status()

    def _copy(self) -> None:
        paths = self._selected_paths()
        if paths:
            self._clipboard = ("copy", paths)
            self._status.showMessage(f"已复制 {len(paths)} 个文件", 2000)

    def _cut(self) -> None:
        paths = self._selected_paths()
        if paths:
            self._clipboard = ("cut", paths)
            self._status.showMessage(f"已剪切 {len(paths)} 个文件", 2000)

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
            self, "复制到…" if mode == "copy" else "移动到…", str(self._dir))
        if not dest:
            return
        self._do_transfer(paths, Path(dest), move=(mode == "move"))
        if mode == "move":
            self.refresh()

    def _do_transfer(self, paths: list[Path], dest: Path, move: bool) -> None:
        failed = []
        for p in paths:
            target = dest / p.name
            # 这里的 resolve() 是对的：判断源和目标是不是同一个文件，必须穿透软链接
            if target.resolve() == p.resolve():
                continue
            target = self._unique_name(target)
            try:
                shutil.move(str(p), str(target)) if move else shutil.copy2(str(p), str(target))
            except OSError as e:
                failed.append(f"{p.name}: {e}")
        if failed:
            QMessageBox.warning(self, "部分操作失败", "\n".join(failed[:10]))
        else:
            verb = "移动" if move else "复制"
            self._status.showMessage(f"已{verb} {len(paths)} 个文件到 {dest}", 3000)

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
