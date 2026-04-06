#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/runtime"

mkdir -p "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR/health"

if [ ! -f "$RUNTIME_DIR/config.json" ]; then
  cp "$ROOT_DIR/config.json" "$RUNTIME_DIR/config.json"
  echo "Copied config.json to runtime/"
fi

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "Created .env from .env.example"
fi

if [ ! -f "$RUNTIME_DIR/bans.db" ]; then
  : > "$RUNTIME_DIR/bans.db"
  echo "Created empty runtime/bans.db"
fi

if [ ! -f "$RUNTIME_DIR/GeoLite2-ASN.mmdb" ]; then
  echo "WARNING: runtime/GeoLite2-ASN.mmdb is missing"
fi

echo "Runtime bootstrap complete."
