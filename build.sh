#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT_DIR"

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  printf '%s\n' "[INFO] Created .env from .env.example"
fi

missing=""
for key in TG_MAIN_BOT_TOKEN TG_ADMIN_BOT_TOKEN TG_ADMIN_BOT_USERNAME IPINFO_TOKEN; do
  if ! grep -q "^${key}=" ".env"; then
    missing="${missing} ${key}"
  fi
done
if ! grep -Eq '^(REMNAWAVE_API_TOKEN|PANEL_TOKEN)=' ".env"; then
  missing="${missing} REMNAWAVE_API_TOKEN"
fi
missing=$(printf '%s' "$missing" | xargs)
if [ -n "$missing" ]; then
  printf '%s\n' "[ERROR] Missing required .env keys: $missing" >&2
  exit 1
fi

mkdir -p runtime runtime/health
[ -f runtime/config.json ] || { printf '%s\n' "[ERROR] runtime/config.json is required" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || { printf '%s\n' "[ERROR] docker not found" >&2; exit 1; }

docker compose build
docker compose run --rm --no-deps mobguard-api python -c "from api.app import app; print(app.title)"
printf '%s\n' "[OK] Panel build and container smoke-check passed"
