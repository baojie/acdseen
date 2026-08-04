"""英文翻译表：id → English。

这是所有 id 的权威清单（i18n.tr 查不到当前语言时回退到这里），
所以每个 id 都必须出现在本表。按来源文件分组，方便对照代码维护。
"""

TRANSLATIONS = {
    # ------------------------------------------------------- config.py
    "sort.name": "Name",
    "sort.size": "File size",
    "sort.type": "Type",
    "sort.date": "Modified",
    "sort.pixels": "Pixels",
    "sort.width": "Width",
    "sort.height": "Height",
    "sort.random": "Random",
    "view.thumbnails": "Thumbnails",
    "view.list": "List",

    # ------------------------------------------------------- menus.py
    "menu.file": "&File",
    "action.open": "Open",
    "action.reveal": "Show in file manager",
    "action.rename": "Rename",
    "action.delete": "Delete",
    "action.copy": "Copy",
    "action.cut": "Cut",
    "action.paste": "Paste into this folder",
    "action.copy_to": "Copy to…",
    "action.move_to": "Move to…",
    "action.quit": "Quit",
    "menu.view": "&View",
    "action.toggle_view": "Toggle thumbnails / list",
    "action.select_all": "Select all",
    "action.refresh": "Refresh",
    "action.thumb_larger": "Enlarge thumbnails",
    "action.thumb_smaller": "Shrink thumbnails",
    "action.toggle_tree": "Toggle folder tree",
    "action.preview_pane": "Preview pane",
    "action.win95": "Windows 95 look",
    "action.clear_cache": "Clear thumbnail cache",
    "menu.language": "Language",
    "menu.sort": "&Sort",
    "sort.by": "By {}",
    "sort.tooltip": "Reads each image's header — slow the first time on big folders",
    "sort.reverse": "Reverse order",
    "menu.show": "&Show",
    "action.view_selected": "View selected image",
    "action.slideshow_first": "Start slideshow from first",
    "menu.help": "&Help",
    "action.shortcuts": "Shortcuts",
    "action.about": "About",
    "about.title": "About {}",
    "about.text": ("A recreation of the 1996 ACDSee 1.2x: one browser + one viewer,<br>"
                   "no database, no editor, no cloud.<br><br>"
                   "It only has to open fast, page smoothly, and keep your hands on the keyboard."),
    "ctx.parent": "Go to parent\tBackspace",
    "ctx.view": "View\tEnter",
    "ctx.slideshow": "Slideshow",
    "ctx.rename": "Rename\tF2",
    "ctx.delete": "Delete\tDel",
    "ctx.copy": "Copy\tCtrl+C",
    "ctx.cut": "Cut\tCtrl+X",
    "ctx.copy_to": "Copy to…",
    "ctx.move_to": "Move to…",

    # ------------------------------------------------------- browser.py
    "status.images": "{} images",
    "status.selected": ", {} selected",
    "msg.cache_cleared": "Thumbnail cache cleared",

    # ------------------------------------------------------- viewer.py
    "fit.window": "Fit window",
    "fit.width": "Fit width",
    "fit.1to1": "Actual size 1:1",
    "fit.fill": "Fill frame",
    "err.decode": "Cannot decode {}",
    "msg.delete_confirm": "Delete {}?",
    "msg.delete_failed": "Delete failed",
    "viewer.next": "Next\tSpace",
    "viewer.prev": "Previous\tBackspace",
    "viewer.fit_window": "Fit window\t*",
    "viewer.fit_fill": "Fill frame\tZ",
    "viewer.fit_width": "Fit width\tW",
    "viewer.actual": "Actual size\t/",
    "viewer.fullscreen": "Fullscreen\tF",
    "viewer.slideshow": "Slideshow\tS",
    "viewer.shuffle": "Shuffle\tR",
    "viewer.delay": "Slideshow delay…\tD (now {})",
    "viewer.delete": "Delete\tDel",
    "viewer.back": "Back to browser\tEsc",

    # ------------------------------------------------------- slideshow.py
    "slideshow.asap": "ASAP",
    "slideshow.seconds": "{:g} s",
    "slideshow.shuffled": ", shuffled",
    "slideshow.stopped": "Slideshow: stopped",
    "slideshow.running": "Slideshow: {} each{}",
    "slideshow.delay_set": "Slideshow delay: {}",
    "shuffle.on": "Shuffle: on",
    "shuffle.off": "Shuffle: off",
    "slideshow.dialog_title": "Slideshow delay",
    "slideshow.dialog_prompt": "Seconds per slide (0 = as soon as possible):",

    # ------------------------------------------------------- render.py
    "osd.refining": "· refining",
    "osd.shuffle": "⤨ shuffle",
    "osd.play": "▶ {}",

    # ------------------------------------------------------- fileops.py
    "rename.title": "Rename",
    "rename.prompt": "New name:",
    "err.exists": "{} already exists.",
    "err.rename_failed": "Rename failed",
    "delete.confirm_many": "Delete the {} selected files?",
    "err.delete_partial": "Some deletions failed",
    "status.copied": "Copied {} file(s)",
    "status.cut": "Cut {} file(s)",
    "verb.move": "Move",
    "verb.copy": "Copy",
    "err.transfer_partial": "Some operations failed",
    "status.transferred": "{verb} {count} file(s) to {dest}",

    # ------------------------------------------------------- thumbmodel.py
    "col.name": "Name",
    "col.dims": "Dimensions",
    "col.size": "Size",
    "col.type": "Type",
    "col.mtime": "Modified",
    "tip.parent": "Parent folder: {}",

    # ------------------------------------------------------- preview.py
    "preview.hint": "Select an image to preview",
    "preview.decoding": "Decoding…",

    # ------------------------------------------------------- helptext.py
    "help.text": "[Browser]\n"
        "  Enter / double-click   View image\n"
        "  Backspace         Go to parent (or click the .. row)\n"
        "  Path bar          Top-right; type a path and press Enter, drop-down for ancestors\n"
        "  F2                Rename\n"
        "  Del               Delete\n"
        "  Ctrl+C / X / V    Copy / Cut / Paste into this folder\n"
        "  Ctrl+Shift+C / M  Copy to… / Move to…\n"
        "  Ctrl++ / Ctrl+-   Enlarge / shrink thumbnails (in list mode switches back)\n"
        "  F5                Refresh\n"
        "  F8                Toggle thumbnails / list\n"
        "  Ctrl+1 / Ctrl+2   Thumbnail mode / List mode\n"
        "  F9                Show / hide folder tree\n"
        "  View → Windows 95 look   Retro beveled skin; can be turned off\n"
        "  Ctrl+S            Start fullscreen slideshow from first image\n"
        "  Right-click → Slideshow   Start fullscreen slideshow from the clicked image\n"
        "\n"
        "[Sorting] Use the Sort menu, or click the column headers in list mode\n"
        "  Name / Size / Type / Modified — file attributes only, fast\n"
        "  Pixels / Width / Height       — reads each image's header; slow the first time on big folders\n"
        "  Random                        — click again for a fresh shuffle\n"
        "  Reverse                       — combines with any of the above\n"
        "\n"
        "  List headers: click to sort by that column, click again to flip order,\n"
        "  switch column to go back to ascending; drag to resize or reorder columns.\n"
        "\n"
        "[Preview pane]\n"
        "  View → Preview pane shows / hides the preview of the selected image\n"
        "\n"
        "[Viewer]\n"
        "  Space / PgDn / →   Next\n"
        "  Backspace / PgUp / ←   Previous\n"
        "  Home / End         First / last\n"
        "  + / -              Zoom in / out\n"
        "  Z                  Fill frame (default: small images are also enlarged to fill)\n"
        "  *                  Fit window (small images are not enlarged — original ACDSee)\n"
        "  /                  Actual size 1:1\n"
        "  W                  Fit width\n"
        "  F / Enter / F11    Toggle fullscreen\n"
        "  S                  Toggle slideshow\n"
        "  R                  Toggle shuffle\n"
        "  D                  Set slideshow delay (any seconds; 0 = ASAP)\n"
        "  [ / ]              Slideshow delay down / up (0 / 0.5 / 1 / 2 / 3 / 5 / 10 / 15 / 30 / 60 s)\n"
        "  I                  Show / hide info bar\n"
        "  Del                Delete current image\n"
        "  Esc                Exit fullscreen / back to browser\n"
        "\n"
        "  Mouse: click to page, drag to pan, wheel to page,\n"
        "        Ctrl+wheel to zoom, middle-click to toggle fill/1:1, double-click fullscreen",

    # ------------------------------------------------------- main.py
    "usage": "Usage: acdseen [directory | image]\n"
        "\n"
        "  acdseen              Open the last directory (or the current one if none)\n"
        "  acdseen ~/Pictures   Open the browser at the given directory\n"
        "  acdseen photo.jpg    View the image fullscreen; other images in the folder join the list\n"
        "\n"
        "Options:\n"
        "  -h, --help       Show this help\n"
        "  -V, --version    Show version",
}
