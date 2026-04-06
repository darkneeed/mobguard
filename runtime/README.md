Place runtime files here for Docker deployment:

- `.env`
- `config.json`
- `bans.db`
- `GeoLite2-ASN.mmdb`
- `health/`

Both `mobguard-core` and `mobguard-api` mount this directory as `/opt/ban_system`.

Use `../scripts/bootstrap-runtime.sh` to create the expected layout.
