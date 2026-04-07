# MobGuard

MobGuard detects abusive use of mobile-only proxy configs, creates review cases, and applies conservative enforcement through:

- `mobguard-core`: log reader, scoring, warnings, bans, Telegram alerts
- `mobguard-api`: admin API, Telegram auth, health, rules persistence
- `mobguard-web`: React panel for queue moderation, rules editing, and quality metrics

The product is designed to be deployed at `/opt/mobguard` behind an external `Caddy` on `https://mobguard.example.com`.

## Server layout

```text
/opt/mobguard
  .env
  docker-compose.yml
  Caddyfile.example
  runtime/
    config.json
    bans.db
    GeoLite2-ASN.mmdb
```

Secrets live in `.env`. Non-secret runtime rules live in `runtime/config.json`.

## Main features

- structured decision engine with `DecisionBundle`
- review queue for `UNSURE`, `PROBABLE_HOME`, and gated `HIGH_HOME`
- `shadow_mode` for safe rollout
- live rule editing from the web panel
- Telegram login for admins
- light/dark/system theme switcher
- health endpoint with heartbeat, IPInfo availability, `score_zero_ratio`, and `asn_missing_ratio`

## Deploy

### 1. Copy project

Put the project on the server at:

```bash
/opt/mobguard
```

### 2. Bootstrap runtime

```bash
cd /opt/mobguard
chmod +x scripts/bootstrap-runtime.sh
./scripts/bootstrap-runtime.sh
```

This creates:

- `.env` from `.env.example` if missing
- `runtime/config.json` from template if missing
- `runtime/bans.db` if missing
- `runtime/health/`

### 3. Fill `.env`

Required secrets:

```env
TG_MAIN_BOT_TOKEN=
TG_ADMIN_BOT_TOKEN=
TG_ADMIN_BOT_USERNAME=
PANEL_TOKEN=
IPINFO_TOKEN=
BAN_SYSTEM_DIR=/opt/mobguard/runtime
MOBGUARD_ENV_FILE=/opt/mobguard/.env
REMNANODE_ACCESS_LOG=/var/log/remnanode/access.log
MOBGUARD_SESSION_COOKIE=mobguard_session
SESSION_COOKIE_SECURE=true
```

### 4. Edit runtime config

Main file:

```text
/opt/mobguard/runtime/config.json
```

Important fields before first launch:

- `settings.review_ui_base_url=https://mobguard.example.com`
- `settings.shadow_mode=true`
- `settings.panel_url=<your Remnawave URL>`
- `admin_tg_ids=[...]`
- `settings.db_file=/opt/mobguard/runtime/bans.db`
- `settings.geoip_db=/opt/mobguard/runtime/GeoLite2-ASN.mmdb`

### 5. Put GeoLite DB in place

```text
/opt/mobguard/runtime/GeoLite2-ASN.mmdb
```

### 6. Start containers

```bash
cd /opt/mobguard
docker compose up -d --build
docker compose ps
```

Expected host exposure:

- `127.0.0.1:8080 -> mobguard-web`

API and core are not published externally.

## Caddy

Use external `Caddy` on the host. Example is in `Caddyfile.example`.

Minimal setup:

```caddy
mobguard.example.com {
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "geolocation=(), microphone=(), camera=()"
    }

    log {
        output file /var/log/caddy/mobguard-access.log
        format console
    }

    reverse_proxy 127.0.0.1:8080
}
```

Then reload:

```bash
sudo systemctl reload caddy
```

## First launch verification

```bash
curl http://127.0.0.1:8080/api/health
```

Check these fields:

- `status`
- `core.healthy`
- `ipinfo_token_present`
- `analysis_24h.score_zero_ratio`
- `analysis_24h.asn_missing_ratio`

If `IPINFO_TOKEN` is missing, scoring will degrade and many cases can end up with `score=0`.

## Why score could become 0

The most important scoring dependency is `IPInfo`:

- no `IPINFO_TOKEN` -> no ASN / no ISP / no hostname
- no ASN -> no `pure_mobile_asns`, `pure_home_asns`, `mixed_asns`
- no hostname / org -> weak keyword detection

MobGuard now warns about this at startup and exposes it in `/api/health`.

## Final domain

The expected production panel URL is:

```text
https://mobguard.example.com
```

## Web panel

Sections:

- `Queue`: moderation queue, severity, quick actions, pagination
- `Rules`: thresholds, policy flags, ASN lists, keywords, admin IDs
- `Quality`: backlog, resolution ratios, noisy ASNs, active patterns

Theme:

- `System`
- `Light`
- `Dark`

Theme preference is local to the browser.

## Configuration model

### Source of truth

- `.env` for secrets only
- `runtime/config.json` for non-secret runtime config

### Editable from the panel

- thresholds
- policy flags
- ASN lists
- keyword lists
- `admin_tg_ids`
- `review_ui_base_url`
- `shadow_mode`

Panel edits are written back to `runtime/config.json`.

## Rollout strategy

Recommended:

1. Start with `shadow_mode=true`
2. Watch queue and quality metrics
3. Confirm `core.healthy=true`
4. Confirm `score_zero_ratio` is sane
5. Only then disable `shadow_mode` if you want punitive path enabled

## Operations

### Check health

```bash
curl http://127.0.0.1:8080/api/health
```

### Rebuild

```bash
cd /opt/mobguard
docker compose up -d --build
```

### Logs

```bash
docker compose logs -f mobguard-core
docker compose logs -f mobguard-api
docker compose logs -f mobguard-web
```

### Backup

Stop core if possible:

```bash
docker compose stop mobguard-core
```

Backup:

- `runtime/bans.db`
- `runtime/bans.db-wal`
- `runtime/bans.db-shm`
- `runtime/config.json`
- `.env`

Then start core again:

```bash
docker compose start mobguard-core
```

### Rollback

- revert `runtime/config.json` for bad rules
- keep `shadow_mode=true`
- rebuild/restart only if code or infra changed

## Development checks

Python tests:

```bash
python -m unittest discover -s tests
```

Frontend build:

```bash
cd web
npm install
npm run build
```
