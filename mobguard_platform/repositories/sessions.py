from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from ..auth import issue_session_token
from .base import SQLiteRepository


def utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


class AdminSessionRepository(SQLiteRepository):
    def create(self, payload: dict[str, Any], session_ttl_hours: int = 24) -> dict[str, Any]:
        token = issue_session_token()
        now = datetime.utcnow().replace(microsecond=0)
        expires_at = now + timedelta(hours=session_ttl_hours)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO admin_sessions (token, telegram_id, username, first_name, payload_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    int(payload["id"]),
                    payload.get("username"),
                    payload.get("first_name"),
                    json.dumps(payload, ensure_ascii=False),
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.commit()
        return {
            "token": token,
            "telegram_id": int(payload["id"]),
            "username": payload.get("username"),
            "first_name": payload.get("first_name"),
            "expires_at": expires_at.isoformat(),
            "subject": payload.get("subject"),
            "auth_method": payload.get("auth_method"),
            "role": payload.get("role"),
            "permissions": list(payload.get("permissions") or []),
            "totp_enabled": bool(payload.get("totp_enabled")),
            "totp_verified": bool(payload.get("totp_verified")),
            "totp_verified_at": payload.get("totp_verified_at"),
            "payload": payload,
        }

    def get(self, token: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT token, telegram_id, username, first_name, payload_json, created_at, expires_at
                FROM admin_sessions
                WHERE token = ?
                """,
                (token,),
            ).fetchone()
        if not row:
            return None
        if row["expires_at"] <= utcnow():
            return None
        session = dict(row)
        payload = json.loads(session.pop("payload_json"))
        session["payload"] = payload
        for key in (
            "subject",
            "auth_method",
            "role",
            "permissions",
            "totp_enabled",
            "totp_verified",
            "totp_verified_at",
        ):
            session[key] = payload.get(key)
        session["username"] = payload.get("username") or session.get("username")
        session["first_name"] = payload.get("first_name") or session.get("first_name")
        session["telegram_id"] = int(payload.get("telegram_id", session.get("telegram_id", 0)) or 0)
        return session

    def delete(self, token: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
            conn.commit()
