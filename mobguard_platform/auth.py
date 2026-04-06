from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any


def verify_telegram_auth(
    payload: dict[str, Any],
    bot_token: str,
    max_age_seconds: int = 86400,
) -> tuple[bool, str]:
    auth_hash = str(payload.get("hash", "")).strip()
    if not auth_hash:
        return False, "Missing Telegram auth hash"

    data = {
        key: str(value)
        for key, value in payload.items()
        if key != "hash" and value not in (None, "")
    }
    data_check_string = "\n".join(f"{key}={data[key]}" for key in sorted(data))
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calculated = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated, auth_hash):
        return False, "Telegram auth hash mismatch"

    auth_date = int(data.get("auth_date", "0") or "0")
    if not auth_date:
        return False, "Missing auth_date"
    if time.time() - auth_date > max_age_seconds:
        return False, "Telegram auth payload expired"
    return True, "ok"


def issue_session_token() -> str:
    return secrets.token_urlsafe(32)
