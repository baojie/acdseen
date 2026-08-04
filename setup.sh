#!/usr/bin/env bash
# ACDSeeN setup: create a virtualenv and install dependencies.
set -euo pipefail

# Change to the script's directory so it works from anywhere
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV_DIR=".venv"

echo "==> Interpreter: $($PYTHON --version 2>&1)"

if [ ! -d "$VENV_DIR" ]; then
    echo "==> Creating virtualenv $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
else
    echo "==> Virtualenv already exists, skipping"
fi

PIP="$VENV_DIR/bin/pip"
echo "==> Upgrading pip"
"$PIP" install --upgrade pip

echo "==> Installing dependencies (see requirements.txt)"
"$PIP" install -r requirements.txt

echo ""
echo "Done. Run ./run.sh to start."
