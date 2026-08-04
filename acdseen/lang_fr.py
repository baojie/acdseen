"""Traduction française : id → français."""

TRANSLATIONS = {
    # ------------------------------------------------------- config.py
    "sort.name": "Nom",
    "sort.size": "Taille du fichier",
    "sort.type": "Type",
    "sort.date": "Modifié",
    "sort.pixels": "Pixels",
    "sort.width": "Largeur",
    "sort.height": "Hauteur",
    "sort.random": "Aléatoire",
    "view.thumbnails": "Vignettes",
    "view.list": "Liste",

    # ------------------------------------------------------- menus.py
    "menu.file": "&Fichier",
    "action.open": "Ouvrir",
    "action.reveal": "Afficher dans le gestionnaire de fichiers",
    "action.rename": "Renommer",
    "action.delete": "Supprimer",
    "action.copy": "Copier",
    "action.cut": "Couper",
    "action.paste": "Coller dans ce dossier",
    "action.copy_to": "Copier vers…",
    "action.move_to": "Déplacer vers…",
    "action.quit": "Quitter",
    "menu.view": "&Affichage",
    "action.toggle_view": "Basculer vignettes / liste",
    "action.select_all": "Tout sélectionner",
    "action.refresh": "Actualiser",
    "action.thumb_larger": "Agrandir les vignettes",
    "action.thumb_smaller": "Réduire les vignettes",
    "action.toggle_tree": "Afficher/masquer l'arborescence",
    "action.preview_pane": "Volet d'aperçu",
    "action.win95": "Aspect Windows 95",
    "action.clear_cache": "Vider le cache de vignettes",
    "menu.language": "Langue",
    "menu.sort": "&Trier",
    "sort.by": "Par {}",
    "sort.tooltip": "Lit l'en-tête de chaque image ; lent la première fois sur les grands dossiers",
    "sort.reverse": "Ordre inverse",
    "menu.show": "&Afficher",
    "action.view_selected": "Afficher l'image sélectionnée",
    "action.slideshow_first": "Démarrer le diaporama depuis la première",
    "menu.help": "&Aide",
    "action.shortcuts": "Raccourcis",
    "action.about": "À propos",
    "about.title": "À propos de {}",
    "about.text": ("Une récréation de l'ACDSee 1.2x de 1996 : un navigateur + un visionneur,<br>"
                   "pas de base de données, pas d'éditeur, pas de cloud.<br><br>"
                   "Il doit seulement ouvrir vite, défiler sans accroc et garder les mains sur le clavier."),
    "ctx.parent": "Aller au dossier parent\tBackspace",
    "ctx.view": "Afficher\tEnter",
    "ctx.slideshow": "Diaporama",
    "ctx.rename": "Renommer\tF2",
    "ctx.delete": "Supprimer\tDel",
    "ctx.copy": "Copier\tCtrl+C",
    "ctx.cut": "Couper\tCtrl+X",
    "ctx.copy_to": "Copier vers…",
    "ctx.move_to": "Déplacer vers…",

    # ------------------------------------------------------- browser.py
    "status.images": "{} images",
    "status.selected": ", {} sélectionnés",
    "msg.cache_cleared": "Cache de vignettes vidé",

    # ------------------------------------------------------- viewer.py
    "fit.window": "Ajuster à la fenêtre",
    "fit.width": "Ajuster à la largeur",
    "fit.1to1": "Taille réelle 1:1",
    "fit.fill": "Remplir le cadre",
    "err.decode": "Impossible de décoder {}",
    "msg.delete_confirm": "Supprimer {} ?",
    "msg.delete_failed": "Échec de la suppression",
    "viewer.next": "Suivant\tSpace",
    "viewer.prev": "Précédent\tBackspace",
    "viewer.fit_window": "Ajuster à la fenêtre\t*",
    "viewer.fit_fill": "Remplir le cadre\tZ",
    "viewer.fit_width": "Ajuster à la largeur\tW",
    "viewer.actual": "Taille réelle\t/",
    "viewer.fullscreen": "Plein écran\tF",
    "viewer.slideshow": "Diaporama\tS",
    "viewer.shuffle": "Aléatoire\tR",
    "viewer.delay": "Intervalle du diaporama…\tD (actuel {})",
    "viewer.delete": "Supprimer\tDel",
    "viewer.back": "Retour au navigateur\tEsc",

    # ------------------------------------------------------- slideshow.py
    "slideshow.asap": "au plus vite",
    "slideshow.seconds": "{:g} s",
    "slideshow.shuffled": ", aléatoire",
    "slideshow.stopped": "Diaporama : arrêté",
    "slideshow.running": "Diaporama : {} chaque{}",
    "slideshow.delay_set": "Intervalle du diaporama : {}",
    "shuffle.on": "Aléatoire : activé",
    "shuffle.off": "Aléatoire : désactivé",
    "slideshow.dialog_title": "Intervalle du diaporama",
    "slideshow.dialog_prompt": "Secondes par image (0 = au plus vite) :",

    # ------------------------------------------------------- render.py
    "osd.refining": "· affinage",
    "osd.shuffle": "⤨ aléatoire",
    "osd.play": "▶ {}",

    # ------------------------------------------------------- fileops.py
    "rename.title": "Renommer",
    "rename.prompt": "Nouveau nom :",
    "err.exists": "{} existe déjà.",
    "err.rename_failed": "Échec du renommage",
    "delete.confirm_many": "Supprimer les {} fichiers sélectionnés ?",
    "err.delete_partial": "Certaines suppressions ont échoué",
    "status.copied": "{} fichier(s) copié(s)",
    "status.cut": "{} fichier(s) coupé(s)",
    "verb.move": "Déplacer",
    "verb.copy": "Copier",
    "err.transfer_partial": "Certaines opérations ont échoué",
    "status.transferred": "{verb} {count} fichier(s) vers {dest}",

    # ------------------------------------------------------- thumbmodel.py
    "col.name": "Nom",
    "col.dims": "Dimensions",
    "col.size": "Taille",
    "col.type": "Type",
    "col.mtime": "Modifié",
    "tip.parent": "Dossier parent : {}",

    # ------------------------------------------------------- preview.py
    "preview.hint": "Sélectionnez une image à prévisualiser",
    "preview.decoding": "Décodage…",

    # ------------------------------------------------------- helptext.py
    "help.text": "[Navigateur]\n"
        "  Entrée / double-clic   Afficher l'image\n"
        "  Backspace         Aller au dossier parent (ou cliquer sur la ligne ..)\n"
        "  Barre de chemin   En haut à droite ; tapez un chemin puis Entrée, menu déroulant pour les ancêtres\n"
        "  F2                Renommer\n"
        "  Suppr             Supprimer\n"
        "  Ctrl+C / X / V    Copier / Couper / Coller dans ce dossier\n"
        "  Ctrl+Maj+C / M    Copier vers… / Déplacer vers…\n"
        "  Ctrl++ / Ctrl+-   Agrandir / réduire les vignettes (en liste revient aux vignettes)\n"
        "  F5                Actualiser\n"
        "  F8                Basculer vignettes / liste\n"
        "  Ctrl+1 / Ctrl+2   Mode vignettes / mode liste\n"
        "  F9                Afficher / masquer l'arborescence\n"
        "  Affichage → Aspect Windows 95   Peau rétro en relief ; peut être désactivée\n"
        "  Ctrl+S            Démarrer le diaporama plein écran depuis la première\n"
        "  Clic droit → Diaporama   Démarrer le diaporama depuis l'image cliquée\n"
        "\n"
        "[Tri] Utilisez le menu Trier, ou cliquez sur les en-têtes en mode liste\n"
        "  Nom / Taille / Type / Modifié — attributs de fichier uniquement, rapide\n"
        "  Pixels / Largeur / Hauteur    — lit l'en-tête de chaque image ; lent la première fois\n"
        "  Aléatoire                     — cliquez à nouveau pour un nouveau mélange\n"
        "  Ordre inverse                 — se combine avec n'importe lequel des précédents\n"
        "\n"
        "  En-têtes de liste : cliquer trie par cette colonne, re-cliquer inverse,\n"
        "  changer de colonne revient à l'ordre croissant ; glisser pour redimensionner ou réordonner.\n"
        "\n"
        "[Volet d'aperçu]\n"
        "  Affichage → Volet d'aperçu affiche / masque l'aperçu de l'image sélectionnée\n"
        "\n"
        "[Visionneur]\n"
        "  Espace / PgSuiv / →   Suivant\n"
        "  Backspace / PgPréc / ←   Précédent\n"
        "  Début / Fin          Première / dernière\n"
        "  + / -                Zoom avant / arrière\n"
        "  Z                    Remplir le cadre (par défaut : les petites sont aussi agrandies)\n"
        "  *                    Ajuster à la fenêtre (les petites ne sont pas agrandies — ACDSee original)\n"
        "  /                    Taille réelle 1:1\n"
        "  W                    Ajuster à la largeur\n"
        "  F / Entrée / F11     Basculer plein écran\n"
        "  S                    Basculer le diaporama\n"
        "  R                    Basculer l'aléatoire\n"
        "  D                    Régler l'intervalle du diaporama (secondes ; 0 = au plus vite)\n"
        "  [ / ]                Intervalle décroissant / croissant (0 / 0,5 / 1 / 2 / 3 / 5 / 10 / 15 / 30 / 60 s)\n"
        "  I                    Afficher / masquer la barre d'informations\n"
        "  Suppr                Supprimer l'image actuelle\n"
        "  Échap                Quitter le plein écran / retour au navigateur\n"
        "\n"
        "  Souris : clic pour défiler, glisser pour déplacer, molette pour défiler,\n"
        "        Ctrl+molette pour zoomer, clic central bascule ajuster/1:1, double-clic plein écran",

    # ------------------------------------------------------- main.py
    "usage": "Utilisation : acdseen [dossier | image]\n"
        "\n"
        "  acdseen              Ouvre le dernier dossier (ou le dossier actuel si aucun)\n"
        "  acdseen ~/Pictures   Ouvre le navigateur sur le dossier indiqué\n"
        "  acdseen photo.jpg    Affiche l'image en plein écran ; les autres rejoignent la liste\n"
        "\n"
        "Options :\n"
        "  -h, --help       Affiche cette aide\n"
        "  -V, --version    Affiche la version",
}
