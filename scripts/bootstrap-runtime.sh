#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$ROOT_DIR/install.sh" ]; then
  printf '%s\n' "[ERROR] Ожидался корневой install.sh в $ROOT_DIR" >&2
  exit 1
fi

exec sh "$ROOT_DIR/install.sh" "$@"
