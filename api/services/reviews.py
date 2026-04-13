from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import HTTPException

from mobguard_platform import review_reason_for_bundle, validate_live_rules_patch
from .modules import _analyze_event
from .runtime_state import panel_client


def _needs_identity_backfill(payload: dict[str, Any]) -> bool:
    return any(payload.get(key) in (None, "") for key in ("uuid", "username", "telegram_id"))


def _lookup_identifier(payload: dict[str, Any]) -> str:
    for key in ("system_id", "telegram_id", "uuid", "username"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _persist_review_identity(store: Any, case_id: int, latest_event_id: int | None, user: dict[str, Any]) -> None:
    uuid = str(user.get("uuid") or "").strip() or None
    username = str(user.get("username") or "").strip() or None
    system_id = user.get("id")
    try:
        normalized_system_id = int(system_id) if system_id is not None else None
    except (TypeError, ValueError):
        normalized_system_id = None
    telegram_id = user.get("telegramId")
    normalized_telegram_id = str(telegram_id).strip() if telegram_id not in (None, "") else None

    with store._connect() as conn:
        conn.execute(
            """
            UPDATE review_cases
            SET uuid = ?, username = ?, system_id = ?, telegram_id = ?
            WHERE id = ?
            """,
            (uuid, username, normalized_system_id, normalized_telegram_id, case_id),
        )
        if latest_event_id is not None:
            conn.execute(
                """
                UPDATE analysis_events
                SET uuid = ?, username = ?, system_id = ?, telegram_id = ?
                WHERE id = ?
                """,
                (uuid, username, normalized_system_id, normalized_telegram_id, latest_event_id),
            )
        conn.commit()


def _backfill_review_case_identity(container: Any, case_id: int) -> bool:
    with container.store._connect() as conn:
        row = conn.execute(
            """
            SELECT id, latest_event_id, uuid, username, system_id, telegram_id
            FROM review_cases
            WHERE id = ?
            """,
            (case_id,),
        ).fetchone()
    if not row:
        return False

    payload = dict(row)
    if not _needs_identity_backfill(payload):
        return False

    identifier = _lookup_identifier(payload)
    if not identifier:
        return False

    user = panel_client(container).get_user_data(identifier)
    if not user:
        return False

    _persist_review_identity(container.store, int(payload["id"]), payload.get("latest_event_id"), user)
    return True


def list_reviews(container: Any, filters: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = container.store.list_review_cases(filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    refreshed = False
    for item in payload.get("items", []):
        if _backfill_review_case_identity(container, int(item["id"])):
            refreshed = True
    return container.store.list_review_cases(filters) if refreshed else payload


def get_review(container: Any, case_id: int) -> dict[str, Any]:
    try:
        _backfill_review_case_identity(container, case_id)
        return container.store.get_review_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def resolve_review(store: Any, case_id: int, resolution: str, actor: str, actor_tg_id: int, note: str) -> dict[str, Any]:
    try:
        return store.resolve_review_case(case_id, resolution.upper(), actor, actor_tg_id, note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def recheck_reviews(
    container: Any,
    filters: dict[str, Any],
    actor: str,
    actor_tg_id: int,
) -> dict[str, Any]:
    try:
        limit = min(max(int(filters.get("limit", 100) or 100), 1), 500)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="limit must be an integer between 1 and 500") from exc

    review_filters = {
        "status": "OPEN",
        "page": 1,
        "page_size": limit,
        "sort": "updated_desc",
    }
    if filters.get("module_id"):
        review_filters["module_id"] = filters["module_id"]
    if filters.get("review_reason"):
        review_filters["review_reason"] = filters["review_reason"]

    listing = list_reviews(container, review_filters)
    rules_state = container.store.get_live_rules_state()
    rules = rules_state["rules"]
    revision = int(rules_state.get("revision") or 0)

    changed_counts: Counter[str] = Counter()
    items: list[dict[str, Any]] = []
    for row in listing.get("items", []):
        case_id = int(row["id"])
        detail = get_review(container, case_id)
        user_data = {
            "uuid": detail.get("uuid"),
            "username": detail.get("username"),
            "id": detail.get("system_id"),
            "telegramId": detail.get("telegram_id"),
            "module_id": detail.get("module_id"),
            "module_name": detail.get("module_name"),
        }
        payload = {
            "uuid": detail.get("uuid"),
            "username": detail.get("username"),
            "system_id": detail.get("system_id"),
            "telegram_id": detail.get("telegram_id"),
            "ip": detail.get("ip"),
            "tag": detail.get("tag"),
        }
        bundle = await _analyze_event(
            container,
            user_data,
            payload,
            rules,
            persist_behavior_state=False,
            persist_decision=False,
        )
        next_review_reason = review_reason_for_bundle(bundle)
        auto_note = (
            f"auto recheck via live rules revision {revision}: "
            f"{bundle.verdict}/{bundle.confidence_band} score={bundle.score}"
        )
        updated = await container.store.async_recheck_review_case(
            case_id,
            user_data,
            str(detail.get("ip") or ""),
            str(detail.get("tag") or ""),
            bundle,
            next_review_reason,
            actor,
            actor_tg_id,
            auto_note,
        )
        if updated["status"] == "SKIPPED":
            changed_counts["closed"] += 1
        else:
            changed_counts["open"] += 1
        if str(detail.get("review_reason") or "") != str(updated.get("review_reason") or ""):
            changed_counts["reason_changed"] += 1
        if str(detail.get("verdict") or "") != str(updated.get("verdict") or ""):
            changed_counts["verdict_changed"] += 1
        if str(detail.get("confidence_band") or "") != str(updated.get("confidence_band") or ""):
            changed_counts["confidence_changed"] += 1
        if int(detail.get("score") or 0) != int(updated.get("score") or 0):
            changed_counts["score_changed"] += 1
        changed_counts["processed"] += 1
        items.append(
            {
                "id": updated["id"],
                "status": updated["status"],
                "review_reason": updated["review_reason"],
                "verdict": updated["verdict"],
                "confidence_band": updated["confidence_band"],
                "score": updated["score"],
                "ip": updated["ip"],
                "module_id": updated.get("module_id"),
            }
        )

    return {
        "items": items,
        "summary": dict(changed_counts),
        "revision": revision,
        "count": len(items),
    }


def get_rules(store: Any) -> dict[str, Any]:
    return store.get_live_rules_state()


def update_rules(
    store: Any,
    payload: dict[str, Any],
    actor: str,
    actor_tg_id: int,
    *,
    expected_revision: int | None = None,
    expected_updated_at: str | None = None,
) -> dict[str, Any]:
    try:
        validate_live_rules_patch(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return store.update_live_rules(
            payload,
            actor,
            actor_tg_id,
            expected_revision=expected_revision,
            expected_updated_at=expected_updated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
