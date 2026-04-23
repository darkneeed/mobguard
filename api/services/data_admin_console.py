from __future__ import annotations

import json
from typing import Any

from ..context import APIContainer


CONSOLE_SOURCE_SYSTEM = "system"
CONSOLE_SOURCE_MODULE_EVENT = "module_event"
CONSOLE_SOURCE_MODULE_HEARTBEAT = "module_heartbeat"


def _parse_json(raw_value: Any, fallback: Any) -> Any:
    if raw_value in (None, ""):
        return fallback
    if isinstance(raw_value, (dict, list)):
        return raw_value
    try:
        return json.loads(str(raw_value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _normalize_level(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"debug", "info", "warn", "warning", "error", "critical"}:
        return "warn" if normalized == "warning" else normalized
    return "info"


def _system_log_query(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    requested_level = str(filters.get("level") or "").strip().lower()
    if requested_level:
        clauses.append("LOWER(level) = ?")
        params.append("warning" if requested_level == "warn" else requested_level)
    if filters.get("q"):
        search = f"%{str(filters['q']).strip()}%"
        clauses.append("(message LIKE ? OR logger_name LIKE ? OR details_json LIKE ?)")
        params.extend([search, search, search])
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


def _module_event_query(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    requested_level = str(filters.get("level") or "").strip().lower()
    if requested_level == "error":
        clauses.append("(LOWER(last_error) != '' OR processing_state = 'failed')")
    elif requested_level == "warn":
        clauses.append("attempt_count > 0 AND LOWER(last_error) = '' AND processing_state != 'failed'")
    elif requested_level == "info":
        clauses.append("LOWER(last_error) = '' AND processing_state != 'failed'")
    if filters.get("module_id"):
        clauses.append("module_id = ?")
        params.append(str(filters["module_id"]).strip())
    if filters.get("q"):
        search = f"%{str(filters['q']).strip()}%"
        clauses.append(
            "(event_uid LIKE ? OR module_name LIKE ? OR ip LIKE ? OR tag LIKE ? OR raw_payload_json LIKE ? OR last_error LIKE ?)"
        )
        params.extend([search] * 6)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


def _module_heartbeat_query(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    requested_level = str(filters.get("level") or "").strip().lower()
    if requested_level == "error":
        clauses.append("(LOWER(mh.status) = 'error' OR LOWER(m.module_health_status) = 'error')")
    elif requested_level == "warn":
        clauses.append(
            "((LOWER(mh.status) = 'warn' OR LOWER(m.module_health_status) = 'warn') AND LOWER(mh.status) != 'error' AND LOWER(m.module_health_status) != 'error')"
        )
    elif requested_level == "info":
        clauses.append("LOWER(mh.status) NOT IN ('warn', 'error')")
    if filters.get("module_id"):
        clauses.append("mh.module_id = ?")
        params.append(str(filters["module_id"]).strip())
    if filters.get("q"):
        search = f"%{str(filters['q']).strip()}%"
        clauses.append("(mh.module_id LIKE ? OR m.module_name LIKE ? OR mh.details_json LIKE ? OR mh.status LIKE ?)")
        params.extend([search] * 4)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


def _system_log_items(conn: Any, filters: dict[str, Any], limit: int) -> tuple[int, list[dict[str, Any]]]:
    where_sql, params = _system_log_query(filters)
    count = conn.execute(
        f"SELECT COUNT(*) AS cnt FROM system_console_events {where_sql}",
        params,
    ).fetchone()["cnt"]
    rows = conn.execute(
        f"""
        SELECT id, service_name, logger_name, level, message, details_json, created_at
        FROM system_console_events
        {where_sql}
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        details = _parse_json(row["details_json"], {})
        items.append(
            {
                "id": f"{CONSOLE_SOURCE_SYSTEM}:{int(row['id'])}",
                "timestamp": str(row["created_at"] or ""),
                "source": CONSOLE_SOURCE_SYSTEM,
                "level": _normalize_level(row["level"]),
                "message": str(row["message"] or ""),
                "service_name": str(row["service_name"] or ""),
                "logger_name": str(row["logger_name"] or ""),
                "module_id": None,
                "module_name": None,
                "event_uid": None,
                "payload": None,
                "meta": details if isinstance(details, dict) else {},
            }
        )
    return int(count or 0), items


def _module_event_level(row: dict[str, Any]) -> str:
    if str(row.get("last_error") or "").strip():
        return "error"
    if str(row.get("processing_state") or "").strip().lower() == "failed":
        return "error"
    if int(row.get("attempt_count") or 0) > 0:
        return "warn"
    return "info"


def _module_event_message(row: dict[str, Any]) -> str:
    module_label = str(row.get("module_name") or row.get("module_id") or "module")
    ip = str(row.get("ip") or "").strip() or "n/a"
    tag = str(row.get("tag") or "").strip() or "n/a"
    event_uid = str(row.get("event_uid") or "").strip() or "n/a"
    state = str(row.get("processing_state") or "queued").strip() or "queued"
    return f"{module_label} accepted event {event_uid} from {ip} tag {tag} [{state}]"


def _module_event_items(conn: Any, filters: dict[str, Any], limit: int) -> tuple[int, list[dict[str, Any]]]:
    where_sql, params = _module_event_query(filters)
    count = conn.execute(
        f"SELECT COUNT(*) AS cnt FROM ingested_raw_events {where_sql}",
        params,
    ).fetchone()["cnt"]
    rows = conn.execute(
        f"""
        SELECT id, event_uid, module_id, module_name, received_at, occurred_at, log_offset,
               subject_uuid, username, system_id, telegram_id, ip, tag, raw_payload_json,
               processing_state, processing_owner, processing_started_at, attempt_count,
               next_attempt_at, last_error, last_error_at, processed_at, analysis_event_id, review_case_id
        FROM ingested_raw_events
        {where_sql}
        ORDER BY COALESCE(received_at, occurred_at) DESC, id DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    items: list[dict[str, Any]] = []
    for raw_row in rows:
        row = dict(raw_row)
        items.append(
            {
                "id": f"{CONSOLE_SOURCE_MODULE_EVENT}:{int(row['id'])}",
                "timestamp": str(row.get("received_at") or row.get("occurred_at") or ""),
                "source": CONSOLE_SOURCE_MODULE_EVENT,
                "level": _module_event_level(row),
                "message": _module_event_message(row),
                "service_name": None,
                "logger_name": None,
                "module_id": str(row.get("module_id") or ""),
                "module_name": str(row.get("module_name") or ""),
                "event_uid": str(row.get("event_uid") or ""),
                "payload": _parse_json(row.get("raw_payload_json"), {}),
                "meta": {
                    "processing_state": str(row.get("processing_state") or ""),
                    "log_offset": row.get("log_offset"),
                    "ip": row.get("ip"),
                    "tag": row.get("tag"),
                    "attempt_count": int(row.get("attempt_count") or 0),
                    "last_error": str(row.get("last_error") or ""),
                    "processed_at": row.get("processed_at"),
                    "analysis_event_id": row.get("analysis_event_id"),
                    "review_case_id": row.get("review_case_id"),
                },
            }
        )
    return int(count or 0), items


def _module_heartbeat_level(row: dict[str, Any]) -> str:
    heartbeat_status = str(row.get("status") or "").strip().lower()
    health_status = str(row.get("module_health_status") or "").strip().lower()
    if heartbeat_status == "error" or health_status == "error":
        return "error"
    if heartbeat_status == "warn" or health_status == "warn":
        return "warn"
    return "info"


def _module_heartbeat_items(conn: Any, filters: dict[str, Any], limit: int) -> tuple[int, list[dict[str, Any]]]:
    where_sql, params = _module_heartbeat_query(filters)
    count = conn.execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM module_heartbeats mh
        LEFT JOIN (
            SELECT module_id, module_name, health_status AS module_health_status, error_text
            FROM modules
        ) m ON m.module_id = mh.module_id
        {where_sql}
        """,
        params,
    ).fetchone()["cnt"]
    rows = conn.execute(
        f"""
        SELECT mh.id, mh.module_id, mh.status, mh.version, mh.protocol_version,
               mh.config_revision_applied, mh.details_json, mh.created_at,
               m.module_name, m.module_health_status, m.error_text
        FROM module_heartbeats mh
        LEFT JOIN (
            SELECT module_id, module_name, health_status AS module_health_status, error_text
            FROM modules
        ) m ON m.module_id = mh.module_id
        {where_sql}
        ORDER BY mh.created_at DESC, mh.id DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    items: list[dict[str, Any]] = []
    for raw_row in rows:
        row = dict(raw_row)
        details = _parse_json(row.get("details_json"), {})
        status = str(row.get("status") or "online").strip() or "online"
        module_label = str(row.get("module_name") or row.get("module_id") or "module")
        items.append(
            {
                "id": f"{CONSOLE_SOURCE_MODULE_HEARTBEAT}:{int(row['id'])}",
                "timestamp": str(row.get("created_at") or ""),
                "source": CONSOLE_SOURCE_MODULE_HEARTBEAT,
                "level": _module_heartbeat_level(row),
                "message": f"{module_label} heartbeat status {status}",
                "service_name": None,
                "logger_name": None,
                "module_id": str(row.get("module_id") or ""),
                "module_name": str(row.get("module_name") or ""),
                "event_uid": None,
                "payload": details if isinstance(details, dict) else {},
                "meta": {
                    "status": status,
                    "version": str(row.get("version") or ""),
                    "protocol_version": str(row.get("protocol_version") or ""),
                    "config_revision_applied": int(row.get("config_revision_applied") or 0),
                    "health_status": str(row.get("module_health_status") or ""),
                    "error_text": str(row.get("error_text") or ""),
                },
            }
        )
    return int(count or 0), items


def list_console_entries(container: APIContainer, filters: dict[str, Any]) -> dict[str, Any]:
    page = max(int(filters.get("page", 1) or 1), 1)
    page_size = min(max(int(filters.get("page_size", 100) or 100), 1), 200)
    requested_source = str(filters.get("source") or "").strip().lower()
    fetch_limit = max(page * page_size, 200)
    source_counts = {
        CONSOLE_SOURCE_SYSTEM: 0,
        CONSOLE_SOURCE_MODULE_EVENT: 0,
        CONSOLE_SOURCE_MODULE_HEARTBEAT: 0,
    }
    items: list[dict[str, Any]] = []

    with container.store._connect() as conn:
        if requested_source in {"", CONSOLE_SOURCE_SYSTEM}:
            count, source_items = _system_log_items(conn, filters, fetch_limit)
            source_counts[CONSOLE_SOURCE_SYSTEM] = count
            items.extend(source_items)
        if requested_source in {"", CONSOLE_SOURCE_MODULE_EVENT}:
            count, source_items = _module_event_items(conn, filters, fetch_limit)
            source_counts[CONSOLE_SOURCE_MODULE_EVENT] = count
            items.extend(source_items)
        if requested_source in {"", CONSOLE_SOURCE_MODULE_HEARTBEAT}:
            count, source_items = _module_heartbeat_items(conn, filters, fetch_limit)
            source_counts[CONSOLE_SOURCE_MODULE_HEARTBEAT] = count
            items.extend(source_items)

    items.sort(key=lambda item: (str(item.get("timestamp") or ""), str(item.get("id") or "")), reverse=True)
    offset = (page - 1) * page_size
    return {
        "items": items[offset : offset + page_size],
        "count": int(sum(source_counts.values())),
        "page": page,
        "page_size": page_size,
        "source_counts": source_counts,
    }
