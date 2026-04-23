# Local Dev Workflow

This setup is intended for real-time UI work, repeatable local profiling, and safe dev-only overrides without editing tracked repo config.

## Local override contract

- Keep the normal local secrets in ignored `.env`.
- Put dev-only overrides in ignored `panel/.env.local.dev`.
- If you run the sibling collector locally, put collector-only overrides in ignored `../module/.env.local.dev`.
- Do not enable `PANEL_LOCAL_BYPASS_TOTP` in tracked files. Keep it blank in `.env.example` and enable it only in `panel/.env.local.dev` when you explicitly want a local owner-session shortcut.

The launcher writes a merged runtime env file into ignored `runtime/dev/env/panel.env` and starts the API with `MOBGUARD_ENV_FILE` pointed at that generated file. The module helper does the same with `../module/runtime-logs/local-dev/env/module.env`.

## What the stack starts

- FastAPI admin API on `http://127.0.0.1:8000`
- Vite dev server with HMR on `http://127.0.0.1:5173`
- Optional sibling `../module` collector when `../module/.env.local.dev` exists
- Fixed `/api/*` Vite proxy to the local backend

## Start / stop / status

From `panel/` on Windows:

```powershell
.\scripts\start-stack.ps1
.\scripts\status-stack.ps1
.\scripts\logs-stack.ps1
.\scripts\stop-stack.ps1
```

From `panel/` on Linux/macOS:

```bash
./scripts/start-stack.sh
./scripts/status-stack.sh
./scripts/logs-stack.sh
./scripts/stop-stack.sh
```

Compatibility wrappers are still available:

```powershell
.\scripts\start-local-dev.ps1
.\scripts\dev-status.ps1
.\scripts\stop-local-dev.ps1
```

The launcher only stops processes it started itself. If `8000` or `5173` is already occupied by some other process, start fails instead of killing unrelated work.

## Local auth

Recommended `panel/.env.local.dev` content:

```dotenv
SESSION_COOKIE_SECURE=false
# Optional dev-only shortcut:
# PANEL_LOCAL_BYPASS_TOTP=true
```

`PANEL_LOCAL_BYPASS_TOTP` defaults to off. When it is absent from the generated runtime env file, local login follows the full owner TOTP challenge flow.

## Logs and runtime state

- API stdout: `runtime/dev/logs/api.stdout.log`
- API stderr: `runtime/dev/logs/api.stderr.log`
- Web stdout: `runtime/dev/logs/web.stdout.log`
- Web stderr: `runtime/dev/logs/web.stderr.log`
- Generated env: `runtime/dev/env/panel.env`
- Audit reports: `runtime/dev/audits/`

Older logs are rotated into ignored `runtime/dev/log-archive/`.

## Local audit harness

Run a repeatable local audit pass from `panel/`:

```powershell
python -m scripts.audit_stack --start --with-feed
```

or:

```bash
python -m scripts.audit_stack --start --with-feed
```

What it does:

1. optionally starts the local stack
2. waits for `/ready`
3. validates `/health` and local auth
4. measures `overview`, `modules`, review queue, review detail, and data-admin endpoints
5. optionally appends synthetic access-log traffic to the local module feed
6. records latency snapshots and SQLite lock-signal counts into `runtime/dev/audits/`

You can also drive the collector feed directly:

```powershell
python -m scripts.synthetic_ingest --access-log ..\module\runtime-logs\local-dev\access.log --count 200 --tag TAG
```

## Local demo data

If you want the panel to stop being empty and immediately show modules, review queue items, and overview metrics:

```powershell
python -m scripts.seed_local_demo
```

The seed script recreates a deterministic local demo set:

- one fresh demo module with a current heartbeat
- several open review cases
- several resolved and skipped cases
- noisy ASN and mixed-provider data for `Overview`

If the panel API is already running, give it about 10-15 seconds for short-lived in-memory caches to expire before refreshing the UI.
