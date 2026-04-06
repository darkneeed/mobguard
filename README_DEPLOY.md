# MobGuard Deploy with External Caddy

## 1. Prepare runtime

```sh
./scripts/bootstrap-runtime.sh
```

Then place these files into `runtime/`:

- `config.json`
- `bans.db`
- `GeoLite2-ASN.mmdb`
- optional `health/`

Fill project `.env` from `.env.example`.

## 2. Edit runtime config

Set at least:

- `settings.review_ui_base_url=https://guard.<your-domain>`
- `settings.shadow_mode=true` for first rollout
- `admin_tg_ids=[...]` with real Telegram admin IDs
- `settings.panel_url` to your Remnawave URL

## 3. Start containers

```sh
docker compose up --build -d
docker compose ps
```

Expected host bind:

- `127.0.0.1:8080 -> mobguard-web`

API is not exposed directly.

## 4. Configure Caddy

Copy `Caddyfile.example` into your host Caddy config and replace `guard.example.com`.

Then reload Caddy:

```sh
sudo systemctl reload caddy
```

## 5. Verify

```sh
curl -I http://127.0.0.1:8080
curl http://127.0.0.1:8080/api/health
```

Open `https://guard.<your-domain>` and verify Telegram login works.

## 6. Rollout order

1. Start with `shadow_mode=true`
2. Review queue and quality metrics for at least one real traffic window
3. Verify `core` heartbeat is healthy in `/api/health`
4. Only then consider disabling `shadow_mode`
