#!/usr/bin/env bash
# ACDSeeN launcher.
# Usage:
#   ./run.sh                  open the last directory (or the current one)
#   ./run.sh ~/Pictures       open the browser on that directory
#   ./run.sh photo.jpg        go straight to full screen on that image
set -euo pipefail

# Change to the script's directory so it works from anywhere
cd "$(dirname "$0")"

VENV_DIR=".venv"
PY="$VENV_DIR/bin/python"

if [ ! -x "$PY" ]; then
    echo "Error: no virtualenv found. Run ./setup.sh first." >&2
    exit 1
fi

if ! "$PY" -c "import PySide6" 2>/dev/null; then
    echo "Error: PySide6 is not installed. Run ./setup.sh" >&2
    exit 1
fi

exec "$PY" -m acdseen "$@"
