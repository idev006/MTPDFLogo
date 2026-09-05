#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
PYTHON_EXE="$VENV_DIR/bin/python"

printf '\n%s\n' '=========================================='
printf '%s\n' ' MTPDFLogo Installer'
printf '%s\n\n' '=========================================='

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    printf '%s\n' "[ERROR] $PYTHON_BIN was not found."
    printf '%s\n\n' 'Please install Python 3.12 or run with PYTHON_BIN=/path/to/python3.12 ./install.sh'
    exit 1
fi

if [ ! -x "$PYTHON_EXE" ]; then
    printf '%s\n' '[1/3] Creating virtual environment...'
    "$PYTHON_BIN" -m venv "$VENV_DIR"
else
    printf '%s\n' '[1/3] Existing virtual environment found.'
fi

printf '%s\n' '[2/3] Updating pip...'
"$PYTHON_EXE" -m pip install --upgrade pip

printf '%s\n' '[3/3] Installing MTPDFLogo and dependencies...'
"$PYTHON_EXE" -m pip install "$PROJECT_DIR"

printf '\n%s\n' 'Installation finished.'
printf '%s\n' 'Run ./start.sh to open MTPDFLogo.'
