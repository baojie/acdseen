# Windows 95 look: what's still missing

*[简体中文](win95-gaps.zh-CN.md)*

A point-by-point comparison of the current implementation against the reference
screenshot (ACDSee 2.4 running on Windows 95, see `acdsee-2.4-win95.png`),
recording what is still absent. **This is a to-do list, not a defect list** —
several entries are deliberate omissions, with the reasoning given below.

What is already implemented lives in `../acdseen/theme.py`: `#C0C0C0` grey, 2px
chiseled borders, `#000080` full-row navy selection, raised header buttons, the
`+/-` boxes and dotted lines in the tree, square-arrow scrollbars, a sunken
segmented status bar, column separators, pale yellow tooltips, yellow folder
icons.

---

## ✅ Priority A — done

> All implemented on 2026-08-03. The original analysis and implementation notes
> are kept below so the reasoning stays visible.

### A1. Antialiasing wasn't turned off for the font ✅

Win95 used MS Sans Serif — a **bitmap font, no antialiasing**. That font doesn't
exist on modern Linux; `theme.ui_font()` was in practice falling back to
`DejaVu Sans` **with antialiasing on**, which softens every glyph and instantly
makes the whole interface read as "modern". This is the easiest thing to
overlook and the single biggest hit to the period feel.

Setting `QFont.StyleStrategy.NoAntialias` is essentially a one-liner. Going
further would mean embedding a freely licensed Win95-style bitmap font.

**Cost**: very low. **Payoff**: high.

**Implemented**: `theme.ui_font()` sets `QFont.NoAntialias` plus
`PreferFullHinting`. Embedding a freely licensed bitmap font was not done — the
fallback to DejaVu Sans with antialiasing off already looks close enough.

### A2. No path bar ✅

The sunken box in the top right of the reference screenshot showing `C:\WINDOWS`,
with a ▼ drop-down arrow at its right edge. It is one of the most conspicuous
controls in the whole image and we had nothing like it — the current directory
appeared only in the window title.

**Implemented**: an editable `QComboBox` in `viewpanes.py` that lists the
ancestor chain in its drop-down and changes directory on Enter.

One trap: inserting items into a `QComboBox` fires the `activated` signal, and
without a guard that recurses from `set_directory` straight back into
`set_directory`. `_sync_path_bar` blocks it with `blockSignals`, and there is a
regression test watching that.

### A3. The list had no `..` parent row ✅

The first row of the file list in the reference screenshot is `..`, with an
upward folder icon, and it is clickable. We only had Backspace — no target to
click.

**Implemented**, and genuinely built on an explicit distinction:

- `_paths` holds images only; the navigation row is represented separately by
  `_parent_dir`, and `_offset()` converts between the two numbering schemes
- Everything external uses **view row numbers** (`index_of` /
  `first_image_row`), everything internal uses **image indices**
  (`image_index` / `image_count`)
- `path_at()` returns `None` for the navigation row — selection, preview and
  file operations all rely on that single guard
- `_start_slideshow(start)` takes an **image index**, not a view row; getting it
  wrong starts every slideshow from the second image

What we walked into: in `_on_thumb`, `index_of` already returns a view row, and
adding the offset a second time emitted an out-of-range `dataChanged` (Qt prints
a `QModelIndex(-1,-1)` warning).

### A4. Drive icons weren't distinguished by type ✅

In the reference screenshot the floppy (3½ Floppy A:), hard disk (Ms-dos_6 C:),
CD-ROM, Network Neighborhood and My Briefcase each have their own icon; we had a
single generic grey box.

**Implemented**: four new 16×16 grids — `FLOPPY` / `CDROM` / `NETWORK` /
`PARENT` — dispatched by `Win95IconProvider` on `QFileIconProvider.IconType`.

**Note the limited payoff**: Linux has no drive letters, so the tree is almost
entirely ordinary folders and the type can only be guessed from mount point
names (`cdrom`, `fd0` and the like). The one that really earns its keep is
`PARENT` — the "up one level" icon on the first row of the list.

---

## Priority B — worth doing, but think first (not done)

### B1. Toolbar

The row of 3D buttons under the menu bar. The reference screenshot crops it out,
but ACDSee 2.x had one.

Before building it we'd have to decide what goes on it — this project has a
narrower feature surface than the original, and padding out a row of buttons is
worse than having none.

### B2. Sort direction as a column-name suffix instead of an arrow

The original appended a symbol to the column name — `Name+` / `Name-` — where we
use Qt's native triangle indicator.

How: build the suffix in `ThumbModel.headerData()` from the current sort order
and turn off `setSortIndicatorShown`. Careful not to fight the Sort menu's sync
logic (see `viewpanes.py::_sync_sort_indicator`).

### B3. The tree root isn't "My Computer"

The reference screenshot's tree grows out of a virtual My Computer node, with
the drives and desktop items hanging below it. We start straight from the
filesystem root `/`.

Linux has no drive letters, so forcing the metaphor would be awkward. A virtual
root carrying `~`, `/`, and the mount points under `/media` would be the sane
version.

### B4. Row height is too loose

The reference screenshot runs about 15px per row; ours are taller. Better tuned
together with the font from A1.

### B5. The selection bar doesn't run the full width

In the reference screenshot the navy on the Desktop row runs all the way to the
right edge of the window, **past the last column boundary**. Our selection
highlight stops at the content width. The original looks more solid for it.

### B6. Image rows have a pale lilac background

The bottom two rows in the reference screenshot (Black Thatch / Blue Rivets) are
pale lilac (around `#e8e8f8`), while the folders and ordinary files above them
are white — the original used background color to mark "this is an image ACDSee
recognizes".

This is not the same thing as the `setAlternatingRowColors` I just turned off:
it isn't alternating rows, it's coloring by **file type**. Our list is all
images, so copying it would produce a wall of lilac. It only becomes meaningful
after B2/C2 (non-image files mixed into the list).

### B7. Tree selection highlights only the text

The Windows entry on the left of the reference screenshot has a grey highlight
that **wraps the text only**, not the full row — while the file list on the
right is full-width. The two controls had different selection styles in the
original; ours are full-row on both sides.

---

## Priority C — deliberately not doing

### C1. Custom-drawn title bar and window frame

The blue gradient title bar with three square buttons across the top of the
reference screenshot. We use the system window decorations, which on Linux will
never look like that.

Doing it means a frameless window we paint ourselves. **The cost is losing the
window manager's native behavior** — edge snapping, `Super` key shortcuts,
multi-monitor handling, per-desktop window rules would all have to be
reimplemented, and getting that right is hard. Not recommended unless the goal
is explicitly a whole-window replica.

### C2. Subfolders mixed into the file list

In the reference screenshot All Users / AppData / Command… are folders, listed
alongside files. Our list holds **images only**.

This isn't a skin question, it's a change to the product definition — "one
directory of images, no recursion, no catalog" is this project's core trade-off
(see the README). If it's ever wanted, the `..` row (A3) was the much smaller
step in that direction.

### C3. File-type icons

BMP / SYS / EXE each have their own icon in the reference screenshot. We show
thumbnails.

**Thumbnails are exactly what ACDSee was for**; swapping them for type icons
would be a regression. The 40px thumbnail in list mode already does the same
identification job.

---

## Reference image

![ACDSee 2.4 on Windows 95](acdsee-2.4-win95.png)

`acdsee-2.4-win95.png` (1430×911) — the ACDSee 2.4 file browser window. It was
captured from a video, so there is a play-button overlay in the middle and a
line of subtitles across the bottom; neither is part of the interface.

Details worth going back to:

- Left: the tree grows from a `My Computer` virtual root, below it
  `3½ Floppy (A:)`, `Ms-dos_6 (C:)`, `Nsoft02 (D:)`, `Network Neighborhood`,
  `My Briefcase` — each type with its own icon. The expanded `Windows` entry is
  highlighted **around the text only**.
- Top right: the `C:\WINDOWS` path bar with a ▼ arrow at its right edge.
- Headers: `Name+` / `Size` / `Image Properties` / `Description` — sort direction
  is a **`+` suffix on the column name**, not an arrow.
- The first row is `..`, with a horizontal-bar "parent directory" icon.
- The `Desktop` row is selected, and the navy runs **full width, to the right
  edge of the window**.
- The bottom two image rows (Black Thatch / Blue Rivets) have a **pale lilac
  background**, and their `Image Properties` column reads `31x30x2 bmp` —
  "width x height x depth, format".
- Status bar: `Total 148 files (7 MB)`.
