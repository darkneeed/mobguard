from __future__ import annotations

from typing import Any

from ..context import APIContainer


def actor_name(session: dict[str, Any]) -> str:
    return (
        str(session.get("username") or "").strip()
        or str(session.get("first_name") or "").strip()
        or str(session.get("subject") or "").strip()
        or f"tg:{int(session.get('telegram_id') or 0)}"
    )


def record_admin_action(
    container: APIContainer,
    session: dict[str, Any],
    *,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return container.store.record_admin_audit_event(
        actor_subject=str(session.get("subject") or ""),
        actor_role=str(session.get("role") or "viewer"),
        actor_auth_method=str(session.get("auth_method") or "unknown"),
        actor_telegram_id=int(session.get("telegram_id") or 0) or None,
        actor_username=actor_name(session),
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
    )
