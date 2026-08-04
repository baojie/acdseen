"""Chinese translation table: id → Chinese."""

TRANSLATIONS = {
    # ------------------------------------------------------- config.py
    "sort.name": "名称",
    "sort.size": "文件大小",
    "sort.type": "类型",
    "sort.date": "修改日期",
    "sort.pixels": "像素总数",
    "sort.width": "宽度",
    "sort.height": "高度",
    "sort.random": "随机",
    "view.thumbnails": "缩略图",
    "view.list": "列表",

    # ------------------------------------------------------- menus.py
    "menu.file": "文件(&F)",
    "action.open": "打开",
    "action.reveal": "在文件管理器中显示",
    "action.rename": "重命名",
    "action.delete": "删除",
    "action.copy": "复制",
    "action.cut": "剪切",
    "action.paste": "粘贴到当前目录",
    "action.copy_to": "复制到…",
    "action.move_to": "移动到…",
    "action.quit": "退出",
    "menu.view": "查看(&V)",
    "action.toggle_view": "切换缩略图 / 列表",
    "action.select_all": "全选",
    "action.refresh": "刷新",
    "action.thumb_larger": "放大缩略图",
    "action.thumb_smaller": "缩小缩略图",
    "action.toggle_tree": "切换目录树",
    "action.preview_pane": "预览窗格",
    "action.win95": "Windows 95 外观",
    "action.clear_cache": "清空缩略图缓存",
    "menu.language": "界面语言",
    "menu.sort": "排序(&S)",
    "sort.by": "按{}",
    "sort.tooltip": "需要读取每个文件的图片头，大目录首次会慢一下",
    "sort.reverse": "倒序",
    "menu.show": "看图(&I)",
    "action.view_selected": "查看选中图片",
    "action.slideshow_first": "从第一张开始幻灯片",
    "menu.help": "帮助(&H)",
    "action.shortcuts": "快捷键",
    "action.about": "关于",
    "about.title": "关于 {}",
    "about.text": ("1996 年 ACDSee 1.2x 的复刻：一个浏览器 + 一个看图器，<br>"
                   "没有数据库，没有编辑器，没有云。<br><br>"
                   "只求打开得快、翻页不卡、手不离键盘。"),
    "ctx.parent": "回到上级目录\tBackspace",
    "ctx.view": "查看\tEnter",
    "ctx.slideshow": "幻灯演示",
    "ctx.rename": "重命名\tF2",
    "ctx.delete": "删除\tDel",
    "ctx.copy": "复制\tCtrl+C",
    "ctx.cut": "剪切\tCtrl+X",
    "ctx.copy_to": "复制到…",
    "ctx.move_to": "移动到…",

    # ------------------------------------------------------- browser.py
    "status.images": "{} 张图片",
    "status.selected": "，已选 {}",
    "msg.cache_cleared": "缩略图缓存已清空",

    # ------------------------------------------------------- viewer.py
    "fit.window": "适应窗口",
    "fit.width": "适应宽度",
    "fit.1to1": "实际大小 1:1",
    "fit.fill": "缩放到显示框",
    "err.decode": "无法解码：{}",
    "msg.delete_confirm": "删除 {}？",
    "msg.delete_failed": "删除失败",
    "viewer.next": "下一张\tSpace",
    "viewer.prev": "上一张\tBackspace",
    "viewer.fit_window": "适应窗口\t*",
    "viewer.fit_fill": "缩放到显示框\tZ",
    "viewer.fit_width": "适应宽度\tW",
    "viewer.actual": "实际大小\t/",
    "viewer.fullscreen": "全屏\tF",
    "viewer.slideshow": "幻灯片\tS",
    "viewer.shuffle": "乱序\tR",
    "viewer.delay": "幻灯间隔…\tD（当前 {}）",
    "viewer.delete": "删除\tDel",
    "viewer.back": "返回浏览\tEsc",

    # ------------------------------------------------------- slideshow.py
    "slideshow.asap": "尽快",
    "slideshow.seconds": "{:g} 秒",
    "slideshow.shuffled": "，乱序",
    "slideshow.stopped": "幻灯片：停止",
    "slideshow.running": "幻灯片：{}/张{}",
    "slideshow.delay_set": "幻灯片间隔：{}",
    "shuffle.on": "乱序：开",
    "shuffle.off": "乱序：关",
    "slideshow.dialog_title": "幻灯片间隔",
    "slideshow.dialog_prompt": "每张停留秒数（0 = 尽快）：",

    # ------------------------------------------------------- render.py
    "osd.refining": "· 精修中",
    "osd.shuffle": "⤨ 乱序",
    "osd.play": "▶ {}",

    # ------------------------------------------------------- fileops.py
    "rename.title": "重命名",
    "rename.prompt": "新名称：",
    "err.exists": "{} 已存在。",
    "err.rename_failed": "重命名失败",
    "delete.confirm_many": "删除选中的 {} 个文件？",
    "err.delete_partial": "部分删除失败",
    "status.copied": "已复制 {} 个文件",
    "status.cut": "已剪切 {} 个文件",
    "verb.move": "移动",
    "verb.copy": "复制",
    "err.transfer_partial": "部分操作失败",
    "status.transferred": "已{verb} {count} 个文件到 {dest}",

    # ------------------------------------------------------- thumbmodel.py
    "col.name": "名称",
    "col.dims": "尺寸",
    "col.size": "大小",
    "col.type": "类型",
    "col.mtime": "修改日期",
    "tip.parent": "上级目录：{}",

    # ------------------------------------------------------- preview.py
    "preview.hint": "选择一张图片查看预览",
    "preview.decoding": "解码中…",

    # ------------------------------------------------------- helptext.py
    "help.text": "【浏览器】\n"
        "  Enter / 双击      查看图片\n"
        "  Backspace         回到上级目录（也可点列表第一行的 ..）\n"
        "  路径栏            右上角，可直接输入路径回车跳转，下拉选各级祖先\n"
        "  F2                重命名\n"
        "  Del               删除\n"
        "  Ctrl+C / X / V    复制 / 剪切 / 粘贴到当前目录\n"
        "  Ctrl+Shift+C / M  复制到… / 移动到…\n"
        "  Ctrl++ / Ctrl+-   缩略图放大 / 缩小（列表模式下按了会切回缩略图）\n"
        "  F5                刷新\n"
        "  F8                切换 缩略图 / 列表\n"
        "  Ctrl+1 / Ctrl+2   缩略图模式 / 列表模式\n"
        "  F9                显示 / 隐藏目录树\n"
        "  菜单「查看 → Windows 95 外观」  灰底立体边框的复古皮肤，可关\n"
        "  Ctrl+S            从第一张开始全屏幻灯片\n"
        "  右键 → 幻灯演示   从右键点中的那张开始全屏幻灯片\n"
        "\n"
        "【排序】菜单「排序」，或在列表模式下点表头\n"
        "  名称 / 文件大小 / 类型 / 修改日期 —— 只看文件属性，快\n"
        "  像素总数 / 宽度 / 高度         —— 要读每个文件的图片头，大目录首次慢一下\n"
        "  随机                           —— 再点一次换一副新牌\n"
        "  倒序                           —— 和上面任意一项叠加\n"
        "\n"
        "  列表模式的表头：点一次按该列排序，再点一次翻转正倒序，\n"
        "  换一列则回到正序；列宽可拖，可拖动调整列顺序。\n"
        "\n"
        "【预览窗格】\n"
        "  菜单「查看 → 预览窗格」显示 / 隐藏选中图片的预览\n"
        "\n"
        "【看图器】\n"
        "  空格 / PgDn / →   下一张\n"
        "  退格 / PgUp / ←   上一张\n"
        "  Home / End        第一张 / 最后一张\n"
        "  + / -             放大 / 缩小\n"
        "  Z                 缩放到显示框（默认：小图也放大，铺满）\n"
        "  *                 适应窗口（小图不放大，ACDSee 原版行为）\n"
        "  /                 实际大小 1:1\n"
        "  W                 适应宽度\n"
        "  F / Enter / F11   全屏切换\n"
        "  S                 幻灯片开关\n"
        "  R                 乱序开关\n"
        "  D                 设定幻灯片间隔（任意秒数，0 = 尽快）\n"
        "  [ / ]             幻灯片间隔 减 / 加（档位 0 / 0.5 / 1 / 2 / 3 / 5 / 10 / 15 / 30 / 60 秒）\n"
        "  I                 显示 / 隐藏信息条\n"
        "  Del               删除当前图片\n"
        "  Esc               退出全屏 / 返回浏览\n"
        "\n"
        "  鼠标：单击翻页，拖拽平移，滚轮翻页，\n"
        "        Ctrl+滚轮 缩放，中键切换 适应/1:1，双击全屏",

    # ------------------------------------------------------- main.py
    "usage": "用法: acdseen [目录 | 图片]\n"
        "\n"
        "  acdseen              打开上次的目录（没有就是当前目录）\n"
        "  acdseen ~/Pictures   打开指定目录的浏览器\n"
        "  acdseen photo.jpg    直接全屏看这张图，同目录其他图自动排进列表\n"
        "\n"
        "选项:\n"
        "  -h, --help       显示此帮助\n"
        "  -V, --version    显示版本",
}
