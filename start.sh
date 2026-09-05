#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_EXE="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON_EXE" ]; then
    printf '%s\n' 'ยังไม่ได้ติดตั้งโปรแกรม'
    printf '%s\n' 'กรุณารัน ./install.sh ก่อน'
    exit 1
fi

export PYTHONPATH="$PROJECT_DIR/app${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON_EXE" -m mtpdflogo "$@"
