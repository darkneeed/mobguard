# MobGuard Runtime Notes

## Live rules

Editable from the web panel without restarting containers:

- thresholds
- policy flags
- ASN lists
- keyword lists
- `admin_tg_ids`
- `review_ui_base_url`

Rules are stored in SQLite `live_rules` with revision tracking and audit rows in `live_rule_audit`.

## Review flow

1. Core writes `analysis_events`
2. Ambiguous or gated HOME decisions create `review_cases`
3. Operator resolves case in web panel
4. Resolution writes:
   - `review_resolutions`
   - `review_labels`
   - `exact_ip_overrides`
5. Promotion job rebuilds `learning_patterns_active`

## Session auth

- Telegram login widget authenticates admin
- API sets `HttpOnly` cookie session
- frontend bootstraps through `/admin/me`

## Shadow mode

With `settings.shadow_mode=true`:

- HOME cases still create warnings and review cases
- punitive path is blocked even if `punitive_eligible=true`

Use this mode for first production rollout.
