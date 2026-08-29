#!/usr/bin/env bash
# Register ACDSeeN with the desktop: icon theme, application menu entry, and
# optionally the dock. Everything is written under ~/.local -- no root, and
# nothing outside the user's own home.
#
# Usage:
#   ./install-desktop.sh            install the icon and the menu entry
#   ./install-desktop.sh --dock     also pin it to the GNOME dock
#   ./install-desktop.sh --uninstall
set -euo pipefail

cd "$(dirname "$0")"
APP_DIR="$(pwd)"
ID="acdseen"
DESKTOP="$HOME/.local/share/applications/$ID.desktop"
ICON_ROOT="$HOME/.local/share/icons/hicolor"
SIZES="16 24 32 48 64 128 256"

pin_to_dock() {
    # favorite-apps is a GVariant array of strings; append only if absent
    local current
    current=$(gsettings get org.gnome.shell favorite-apps)
    if [[ "$current" == *"'$ID.desktop'"* ]]; then
        echo "Already in the dock."
        return
    fi
    gsettings set org.gnome.shell favorite-apps \
        "$(python3 - "$current" "$ID.desktop" <<'PY'
import ast, sys
apps = ast.literal_eval(sys.argv[1])
apps.append(sys.argv[2])
print(str(apps))
PY
)"
    echo "Pinned to the dock."
}

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$DESKTOP"
    for s in $SIZES; do rm -f "$ICON_ROOT/${s}x${s}/apps/$ID.png"; done
    current=$(gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo "[]")
    if [[ "$current" == *"'$ID.desktop'"* ]]; then
        gsettings set org.gnome.shell favorite-apps \
            "$(python3 - "$current" "$ID.desktop" <<'PY'
import ast, sys
apps = [a for a in ast.literal_eval(sys.argv[1]) if a != sys.argv[2]]
print(str(apps))
PY
)"
    fi
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    echo "Removed."
    exit 0
fi

PY="$APP_DIR/.venv/bin/python"
[ -x "$PY" ] || { echo "Error: no virtualenv found. Run ./setup.sh first." >&2; exit 1; }

# The icon is drawn by the app itself, so rendering it needs Qt but no display
for s in $SIZES; do
    QT_QPA_PLATFORM=offscreen "$PY" -c "
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
QApplication([])
from acdseen import appicon
appicon.export_png(Path(sys.argv[1]), int(sys.argv[2]))
" "$ICON_ROOT/${s}x${s}/apps/$ID.png" "$s"
done

mkdir -p "$(dirname "$DESKTOP")"
cat > "$DESKTOP" <<DESK
[Desktop Entry]
Type=Application
Version=1.0
Name=ACDSeeN
Comment=Browse and view images, the way ACDSee 1.2x did
Exec=$APP_DIR/run.sh %f
Icon=$ID
Terminal=false
Categories=Graphics;Viewer;RasterGraphics;
MimeType=image/jpeg;image/png;image/gif;image/bmp;image/tiff;image/webp;
StartupWMClass=$ID
DESK
chmod +x "$DESKTOP"

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true
echo "Installed $DESKTOP"

[ "${1:-}" = "--dock" ] && pin_to_dock
exit 0
