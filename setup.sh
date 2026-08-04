#!/usr/bin/env bash
# ACDSeeN setup: create a virtualenv and install dependencies.
#
# Safe to re-run: an existing .venv is reused rather than rebuilt.
# Override the interpreter with PYTHON=python3.12 ./setup.sh
set -euo pipefail

# Change to the script's directory so it works from anywhere
cd "$(dirname "$0")"

# run.sh looks for the interpreter at exactly this path -- keep them in sync
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

# An outdated pip can fail on PySide6's wheels, so upgrade before installing
echo "==> Upgrading pip"
"$PIP" install --upgrade pip

# Runtime dependencies only. Test dependencies live in requirements-dev.txt
echo "==> Installing dependencies (see requirements.txt)"
"$PIP" install -r requirements.txt

echo ""
echo "Done. Run ./run.sh to start."
