"""Traducción al español: id → español."""

TRANSLATIONS = {
    # ------------------------------------------------------- config.py
    "sort.name": "Nombre",
    "sort.size": "Tamaño del archivo",
    "sort.type": "Tipo",
    "sort.date": "Modificado",
    "sort.pixels": "Píxeles",
    "sort.width": "Ancho",
    "sort.height": "Alto",
    "sort.random": "Aleatorio",
    "view.thumbnails": "Miniaturas",
    "view.list": "Lista",

    # ------------------------------------------------------- menus.py
    "menu.file": "&Archivo",
    "action.open": "Abrir",
    "action.reveal": "Mostrar en el administrador de archivos",
    "action.rename": "Renombrar",
    "action.delete": "Eliminar",
    "action.copy": "Copiar",
    "action.cut": "Cortar",
    "action.paste": "Pegar en esta carpeta",
    "action.copy_to": "Copiar a…",
    "action.move_to": "Mover a…",
    "action.quit": "Salir",
    "menu.view": "&Ver",
    "action.toggle_view": "Alternar miniaturas / lista",
    "action.select_all": "Seleccionar todo",
    "action.refresh": "Actualizar",
    "action.thumb_larger": "Agrandar miniaturas",
    "action.thumb_smaller": "Encoger miniaturas",
    "action.toggle_tree": "Alternar árbol de carpetas",
    "action.preview_pane": "Panel de vista previa",
    "action.win95": "Apariencia Windows 95",
    "action.clear_cache": "Vaciar caché de miniaturas",
    "menu.language": "Idioma",
    "menu.sort": "&Ordenar",
    "sort.by": "Por {}",
    "sort.tooltip": "Lee la cabecera de cada imagen; la primera vez tarda en carpetas grandes",
    "sort.reverse": "Orden inverso",
    "menu.show": "&Mostrar",
    "action.view_selected": "Ver imagen seleccionada",
    "action.slideshow_first": "Iniciar presentación desde la primera",
    "menu.help": "&Ayuda",
    "action.shortcuts": "Atajos",
    "action.about": "Acerca de",
    "about.title": "Acerca de {}",
    "about.text": ("Una recreación del ACDSee 1.2x de 1996: un navegador + un visor,<br>"
                   "sin base de datos, sin editor, sin nube.<br><br>"
                   "Solo tiene que abrir rápido, pasar páginas con fluidez y no soltar el teclado."),
    "ctx.parent": "Ir al directorio padre\tBackspace",
    "ctx.view": "Ver\tEnter",
    "ctx.slideshow": "Presentación",
    "ctx.rename": "Renombrar\tF2",
    "ctx.delete": "Eliminar\tDel",
    "ctx.copy": "Copiar\tCtrl+C",
    "ctx.cut": "Cortar\tCtrl+X",
    "ctx.copy_to": "Copiar a…",
    "ctx.move_to": "Mover a…",

    # ------------------------------------------------------- browser.py
    "status.images": "{} imágenes",
    "status.selected": ", {} seleccionados",
    "msg.cache_cleared": "Caché de miniaturas vaciada",

    # ------------------------------------------------------- viewer.py
    "fit.window": "Ajustar a la ventana",
    "fit.width": "Ajustar al ancho",
    "fit.1to1": "Tamaño real 1:1",
    "fit.fill": "Rellenar el marco",
    "err.decode": "No se puede decodificar {}",
    "msg.delete_confirm": "¿Eliminar {}?",
    "msg.delete_failed": "Error al eliminar",
    "viewer.next": "Siguiente\tSpace",
    "viewer.prev": "Anterior\tBackspace",
    "viewer.fit_window": "Ajustar a la ventana\t*",
    "viewer.fit_fill": "Rellenar marco\tZ",
    "viewer.fit_width": "Ajustar ancho\tW",
    "viewer.actual": "Tamaño real\t/",
    "viewer.fullscreen": "Pantalla completa\tF",
    "viewer.slideshow": "Presentación\tS",
    "viewer.shuffle": "Aleatorio\tR",
    "viewer.delay": "Intervalo de presentación…\tD (ahora {})",
    "viewer.delete": "Eliminar\tDel",
    "viewer.back": "Volver al navegador\tEsc",

    # ------------------------------------------------------- slideshow.py
    "slideshow.asap": "cuanto antes",
    "slideshow.seconds": "{:g} s",
    "slideshow.shuffled": ", aleatorio",
    "slideshow.stopped": "Presentación: detenida",
    "slideshow.running": "Presentación: {} cada{}",
    "slideshow.delay_set": "Intervalo de presentación: {}",
    "shuffle.on": "Aleatorio: activado",
    "shuffle.off": "Aleatorio: desactivado",
    "slideshow.dialog_title": "Intervalo de presentación",
    "slideshow.dialog_prompt": "Segundos por imagen (0 = cuanto antes):",

    # ------------------------------------------------------- render.py
    "osd.refining": "· refinando",
    "osd.shuffle": "⤨ aleatorio",
    "osd.play": "▶ {}",

    # ------------------------------------------------------- fileops.py
    "rename.title": "Renombrar",
    "rename.prompt": "Nuevo nombre:",
    "err.exists": "{} ya existe.",
    "err.rename_failed": "Error al renombrar",
    "delete.confirm_many": "¿Eliminar los {} archivos seleccionados?",
    "err.delete_partial": "Algunas eliminaciones fallaron",
    "status.copied": "{} archivo(s) copiado(s)",
    "status.cut": "{} archivo(s) cortado(s)",
    "verb.move": "Mover",
    "verb.copy": "Copiar",
    "err.transfer_partial": "Algunas operaciones fallaron",
    "status.transferred": "{verb} {count} archivo(s) a {dest}",

    # ------------------------------------------------------- thumbmodel.py
    "col.name": "Nombre",
    "col.dims": "Dimensiones",
    "col.size": "Tamaño",
    "col.type": "Tipo",
    "col.mtime": "Modificado",
    "tip.parent": "Carpeta padre: {}",

    # ------------------------------------------------------- preview.py
    "preview.hint": "Seleccione una imagen para previsualizar",
    "preview.decoding": "Decodificando…",

    # ------------------------------------------------------- helptext.py
    "help.text": "[Navegador]\n"
        "  Enter / doble clic   Ver imagen\n"
        "  Backspace         Ir al directorio padre (o clic en la fila ..)\n"
        "  Barra de ruta     Arriba a la derecha; escriba una ruta y pulse Enter, desplegable para los ancestros\n"
        "  F2                Renombrar\n"
        "  Del               Eliminar\n"
        "  Ctrl+C / X / V    Copiar / Cortar / Pegar en esta carpeta\n"
        "  Ctrl+Shift+C / M  Copiar a… / Mover a…\n"
        "  Ctrl++ / Ctrl+-   Agrandar / encoger miniaturas (en lista vuelve a miniaturas)\n"
        "  F5                Actualizar\n"
        "  F8                Alternar miniaturas / lista\n"
        "  Ctrl+1 / Ctrl+2   Modo miniaturas / modo lista\n"
        "  F9                Mostrar / ocultar árbol de carpetas\n"
        "  Ver → Apariencia Windows 95   Piel retro con relieves; se puede apagar\n"
        "  Ctrl+S            Iniciar presentación a pantalla completa desde la primera\n"
        "  Botón derecho → Presentación   Iniciar presentación desde la imagen pulsada\n"
        "\n"
        "[Ordenar] Use el menú Ordenar, o pulse los encabezados en modo lista\n"
        "  Nombre / Tamaño / Tipo / Modificado — solo atributos, rápido\n"
        "  Píxeles / Ancho / Alto             — lee la cabecera de cada imagen; tarda la primera vez\n"
        "  Aleatorio                          — vuelva a pulsar para barajar de nuevo\n"
        "  Orden inverso                      — se combina con cualquiera de los anteriores\n"
        "\n"
        "  Encabezados de lista: pulse para ordenar por esa columna, pulse de nuevo para invertir,\n"
        "  cambie de columna para volver a ascendente; arrastre para ajustar ancho u orden.\n"
        "\n"
        "[Panel de vista previa]\n"
        "  Ver → Panel de vista previa muestra / oculta la vista previa de la imagen seleccionada\n"
        "\n"
        "[Visor]\n"
        "  Espacio / PgDn / →   Siguiente\n"
        "  Backspace / PgUp / ←   Anterior\n"
        "  Inicio / Fin         Primera / última\n"
        "  + / -                Acercar / alejar\n"
        "  Z                    Rellenar marco (por defecto: las pequeñas también se agrandan)\n"
        "  *                    Ajustar a la ventana (las pequeñas no se agrandan — ACDSee original)\n"
        "  /                    Tamaño real 1:1\n"
        "  W                    Ajustar al ancho\n"
        "  F / Enter / F11      Alternar pantalla completa\n"
        "  S                    Alternar presentación\n"
        "  R                    Alternar aleatorio\n"
        "  D                    Fijar intervalo de presentación (segundos; 0 = cuanto antes)\n"
        "  [ / ]                Intervalo hacia abajo / arriba (0 / 0.5 / 1 / 2 / 3 / 5 / 10 / 15 / 30 / 60 s)\n"
        "  I                    Mostrar / ocultar barra de información\n"
        "  Del                  Eliminar imagen actual\n"
        "  Esc                  Salir de pantalla completa / volver al navegador\n"
        "\n"
        "  Ratón: clic para pasar página, arrastre para mover, rueda para pasar página,\n"
        "        Ctrl+rueda para zoom, clic central alterna ajustar/1:1, doble clic pantalla completa",

    # ------------------------------------------------------- main.py
    "usage": "Uso: acdseen [directorio | imagen]\n"
        "\n"
        "  acdseen              Abre el último directorio (o el actual si no hay)\n"
        "  acdseen ~/Pictures   Abre el navegador en el directorio indicado\n"
        "  acdseen photo.jpg    Ve la imagen a pantalla completa; las demás se unen a la lista\n"
        "\n"
        "Opciones:\n"
        "  -h, --help       Muestra esta ayuda\n"
        "  -V, --version    Muestra la versión",
}
