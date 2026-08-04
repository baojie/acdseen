"""日本語翻訳表：id → 日本語。"""

TRANSLATIONS = {
    # ------------------------------------------------------- config.py
    "sort.name": "名前",
    "sort.size": "ファイルサイズ",
    "sort.type": "種類",
    "sort.date": "更新日時",
    "sort.pixels": "総ピクセル数",
    "sort.width": "幅",
    "sort.height": "高さ",
    "sort.random": "ランダム",
    "view.thumbnails": "サムネイル",
    "view.list": "リスト",

    # ------------------------------------------------------- menus.py
    "menu.file": "ファイル(&F)",
    "action.open": "開く",
    "action.reveal": "ファイルマネージャーで表示",
    "action.rename": "名前を変更",
    "action.delete": "削除",
    "action.copy": "コピー",
    "action.cut": "切り取り",
    "action.paste": "このフォルダーに貼り付け",
    "action.copy_to": "コピー先…",
    "action.move_to": "移動先…",
    "action.quit": "終了",
    "menu.view": "表示(&V)",
    "action.toggle_view": "サムネイル / リスト切替",
    "action.select_all": "すべて選択",
    "action.refresh": "更新",
    "action.thumb_larger": "サムネイルを拡大",
    "action.thumb_smaller": "サムネイルを縮小",
    "action.toggle_tree": "フォルダーツリー表示切替",
    "action.preview_pane": "プレビュー欄",
    "action.win95": "Windows 95 風外観",
    "action.clear_cache": "サムネイルキャッシュを消去",
    "menu.language": "言語",
    "menu.sort": "並べ替え(&S)",
    "sort.by": "{}順",
    "sort.tooltip": "画像ヘッダーを読みます。大きいフォルダーでは初回が遅くなります",
    "sort.reverse": "逆順",
    "menu.show": "スライド(&I)",
    "action.view_selected": "選択画像を表示",
    "action.slideshow_first": "最初からスライドショー",
    "menu.help": "ヘルプ(&H)",
    "action.shortcuts": "ショートカット",
    "action.about": "バージョン情報",
    "about.title": "{} について",
    "about.text": ("1996 年の ACDSee 1.2x の復刻：ブラウザ + ビューア。<br>"
                   "データベースもエディタもクラウドもなし。<br><br>"
                   "速く開けて、ページ送りも滑らか、手をキーボードから離さない。"),
    "ctx.parent": "親フォルダーへ戻る\tBackspace",
    "ctx.view": "表示\tEnter",
    "ctx.slideshow": "スライドショー",
    "ctx.rename": "名前を変更\tF2",
    "ctx.delete": "削除\tDel",
    "ctx.copy": "コピー\tCtrl+C",
    "ctx.cut": "切り取り\tCtrl+X",
    "ctx.copy_to": "コピー先…",
    "ctx.move_to": "移動先…",

    # ------------------------------------------------------- browser.py
    "status.images": "{} 枚の画像",
    "status.selected": "、{} 件選択",
    "msg.cache_cleared": "サムネイルキャッシュを消去しました",

    # ------------------------------------------------------- viewer.py
    "fit.window": "ウィンドウに合わせる",
    "fit.width": "幅に合わせる",
    "fit.1to1": "実寸 1:1",
    "fit.fill": "フレームに合わせる",
    "err.decode": "{} をデコードできません",
    "msg.delete_confirm": "{} を削除しますか？",
    "msg.delete_failed": "削除に失敗",
    "viewer.next": "次へ\tSpace",
    "viewer.prev": "前へ\tBackspace",
    "viewer.fit_window": "ウィンドウに合わせる\t*",
    "viewer.fit_fill": "フレームに合わせる\tZ",
    "viewer.fit_width": "幅に合わせる\tW",
    "viewer.actual": "実寸\t/",
    "viewer.fullscreen": "全画面\tF",
    "viewer.slideshow": "スライドショー\tS",
    "viewer.shuffle": "シャッフル\tR",
    "viewer.delay": "スライド間隔…\tD（現在 {}）",
    "viewer.delete": "削除\tDel",
    "viewer.back": "ブラウザに戻る\tEsc",

    # ------------------------------------------------------- slideshow.py
    "slideshow.asap": "即時",
    "slideshow.seconds": "{:g} 秒",
    "slideshow.shuffled": "、シャッフル",
    "slideshow.stopped": "スライドショー：停止",
    "slideshow.running": "スライドショー：{} ごと{}",
    "slideshow.delay_set": "スライド間隔：{}",
    "shuffle.on": "シャッフル：オン",
    "shuffle.off": "シャッフル：オフ",
    "slideshow.dialog_title": "スライド間隔",
    "slideshow.dialog_prompt": "1 枚あたりの秒数（0 = 即時）：",

    # ------------------------------------------------------- render.py
    "osd.refining": "· 調整中",
    "osd.shuffle": "⤨ シャッフル",
    "osd.play": "▶ {}",

    # ------------------------------------------------------- fileops.py
    "rename.title": "名前を変更",
    "rename.prompt": "新しい名前：",
    "err.exists": "{} は既に存在します。",
    "err.rename_failed": "名前の変更に失敗",
    "delete.confirm_many": "選択した {} 個のファイルを削除しますか？",
    "err.delete_partial": "一部の削除に失敗",
    "status.copied": "{} 個のファイルをコピーしました",
    "status.cut": "{} 個のファイルを切り取りました",
    "verb.move": "移動",
    "verb.copy": "コピー",
    "err.transfer_partial": "一部の操作に失敗",
    "status.transferred": "{count} 個のファイルを {dest} に{verb}しました",

    # ------------------------------------------------------- thumbmodel.py
    "col.name": "名前",
    "col.dims": "寸法",
    "col.size": "サイズ",
    "col.type": "種類",
    "col.mtime": "更新日時",
    "tip.parent": "親フォルダー：{}",

    # ------------------------------------------------------- preview.py
    "preview.hint": "プレビューする画像を選択",
    "preview.decoding": "デコード中…",

    # ------------------------------------------------------- helptext.py
    "help.text": "[ブラウザ]\n"
        "  Enter / ダブルクリック  画像を表示\n"
        "  Backspace         親フォルダーへ（リスト先頭の .. をクリックでも）\n"
        "  パスバー           右上。パスを入力して Enter、祖先フォルダーのドロップダウン\n"
        "  F2                名前を変更\n"
        "  Del               削除\n"
        "  Ctrl+C / X / V    コピー / 切り取り / このフォルダーに貼り付け\n"
        "  Ctrl+Shift+C / M  コピー先… / 移動先…\n"
        "  Ctrl++ / Ctrl+-   サムネイル拡大 / 縮小（リスト中はサムネイルに戻る）\n"
        "  F5                更新\n"
        "  F8                サムネイル / リスト切替\n"
        "  Ctrl+1 / Ctrl+2   サムネイル表示 / リスト表示\n"
        "  F9                フォルダーツリー表示 / 非表示\n"
        "  「表示 → Windows 95 風外観」  レトロな立体外観、オフ可\n"
        "  Ctrl+S            最初から全画面スライドショー\n"
        "  右クリック → スライドショー  その画像から全画面スライドショー\n"
        "\n"
        "[並べ替え]「並べ替え」メニュー、またはリストでヘッダーをクリック\n"
        "  名前 / ファイルサイズ / 種類 / 更新日時 —— ファイル属性のみ、速い\n"
        "  総ピクセル数 / 幅 / 高さ   —— 画像ヘッダーを読むため、初回は遅い\n"
        "  ランダム                   —— もう一度クリックでシャッフルし直し\n"
        "  逆順                       —— 上記のどれとも組み合わせ可\n"
        "\n"
        "  リストのヘッダー：クリックでその列で並べ替え、もう一度で逆順、\n"
        "  別の列なら昇順に戻る。幅と順序はドラッグで調整。\n"
        "\n"
        "[プレビュー欄]\n"
        "  「表示 → プレビュー欄」で選択画像のプレビューを表示 / 非表示\n"
        "\n"
        "[ビューア]\n"
        "  スペース / PgDn / →   次へ\n"
        "  Backspace / PgUp / ←  前へ\n"
        "  Home / End        最初 / 最後\n"
        "  + / -             拡大 / 縮小\n"
        "  Z                 フレームに合わせる（既定：小画像も拡大して埋める）\n"
        "  *                 ウィンドウに合わせる（小画像は拡大しない — 原版）\n"
        "  /                 実寸 1:1\n"
        "  W                 幅に合わせる\n"
        "  F / Enter / F11   全画面切替\n"
        "  S                 スライドショー切替\n"
        "  R                 シャッフル切替\n"
        "  D                 スライド間隔を設定（任意秒数、0 = 即時）\n"
        "  [ / ]             スライド間隔 減 / 増（0 / 0.5 / 1 / 2 / 3 / 5 / 10 / 15 / 30 / 60 秒）\n"
        "  I                 情報バー表示 / 非表示\n"
        "  Del               現在の画像を削除\n"
        "  Esc               全画面終了 / ブラウザに戻る\n"
        "\n"
        "  マウス：クリックでページ送り、ドラッグでパン、ホイールでページ送り、\n"
        "        Ctrl+ホイールでズーム、中クリックで 合わせる/1:1 切替、ダブルクリックで全画面",

    # ------------------------------------------------------- main.py
    "usage": "使い方: acdseen [ディレクトリ | 画像]\n"
        "\n"
        "  acdseen              前回のディレクトリを開く（なければ現在のディレクトリ）\n"
        "  acdseen ~/Pictures   指定したディレクトリのブラウザを開く\n"
        "  acdseen photo.jpg    画像を全画面で表示、同フォルダーの他の画像もリストに\n"
        "\n"
        "オプション:\n"
        "  -h, --help       このヘルプを表示\n"
        "  -V, --version    バージョンを表示",
}
