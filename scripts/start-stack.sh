#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python}"
exec "$PYTHON_BIN" -m scripts.dev_stack start "$@"
