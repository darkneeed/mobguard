# MobGuard Operations

## Daily checks

- Open `/api/health` through the panel or `curl http://127.0.0.1:8080/api/health`
- Confirm `core.healthy=true`
- Review open queue backlog
- Check latest live rules revision in Quality page

## Editing rules

- Use the `Rules` page
- Save only one logical batch at a time
- If save returns revision conflict, reload page and re-apply changes

## Moderation

- Prioritize `critical` severity first
- Use queue quick actions for obvious cases
- Open case detail for linked IP/user context before resolving borderline cases

## Backup

Stop writes first when possible:

```sh
docker compose stop mobguard-core
```

Backup `runtime/bans.db`, `runtime/bans.db-wal`, `runtime/bans.db-shm`, `runtime/config.json`, `.env`.

Then restart:

```sh
docker compose start mobguard-core
```

## Rollback

- Revert `runtime/config.json` if a bad rule rollout caused regressions
- Keep `shadow_mode=true` during investigation
- Restart compose only if infrastructure settings changed
