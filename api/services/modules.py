from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from behavioral_analyzers import BehavioralEngine
from ipinfo_api import ipinfo_api
from mobguard_core.scoring import ScoringContext, ScoringDependencies, evaluate_mobile_network
from mobguard_platform import (
    DecisionBundle,
    apply_remote_access_state,
    apply_remote_traffic_cap,
    build_auto_restriction_state,
    review_reason_for_bundle,
    should_warning_only,
)
from mobguard_platform.panel_client import PanelClient
from mobguard_platform.runtime_admin_defaults import ENFORCEMENT_SETTINGS_DEFAULTS

from ..context import APIContainer


PROTOCOL_VERSION = "v1"


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _require_protocol_version(protocol_version: str) -> str:
    normalized = str(protocol_version or "").strip() or PROTOCOL_VERSION
    if normalized != PROTOCOL_VERSION:
        raise ValueError(f"Unsupported module protocol version: {normalized}")
    return normalized


def _runtime_settings(container: APIContainer) -> dict[str, Any]:
    return container.store.get_live_rules_state()["rules"].get("settings", {})


def _module_runtime(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "heartbeat_interval_seconds": int(settings.get("module_heartbeat_interval_seconds", 30)),
        "config_poll_interval_seconds": int(settings.get("module_config_poll_interval_seconds", 60)),
        "flush_interval_seconds": int(settings.get("module_flush_interval_seconds", 3)),
        "event_batch_size": int(settings.get("module_event_batch_size", 100)),
        "max_spool_events": int(settings.get("module_max_spool_events", 5000)),
    }


def _remnawave_client(container: APIContainer) -> PanelClient:
    settings = _runtime_settings(container)
    base_url = str(settings.get("remnawave_api_url") or settings.get("panel_url") or "").strip()
    token = (
        os.getenv("REMNAWAVE_API_TOKEN")
        or os.getenv("PANEL_TOKEN")
        or ""
    )
    return PanelClient(base_url, token)


def _event_uid(module_id: str, payload: dict[str, Any]) -> str:
    raw_uid = str(payload.get("event_uid") or "").strip()
    if raw_uid:
        return raw_uid
    fallback = "|".join(
        [
            str(module_id),
            str(payload.get("log_offset") or ""),
            str(payload.get("occurred_at") or ""),
            str(payload.get("uuid") or ""),
            str(payload.get("system_id") or ""),
            str(payload.get("telegram_id") or ""),
            str(payload.get("ip") or ""),
            str(payload.get("tag") or ""),
        ]
    )
    return hashlib.sha256(fallback.encode("utf-8")).hexdigest()


async def _resolve_remote_user(
    container: APIContainer,
    client: PanelClient,
    payload: dict[str, Any],
) -> dict[str, Any]:
    identifier = next(
        (
            value
            for value in (
                payload.get("uuid"),
                payload.get("system_id"),
                payload.get("telegram_id"),
                payload.get("username"),
            )
            if value not in (None, "")
        ),
        None,
    )
    remote_user = {}
    if identifier not in (None, "") and client.enabled:
        remote_user = await asyncio.to_thread(client.get_user_data, str(identifier).strip()) or {}
    user_data = dict(remote_user)
    if payload.get("uuid") and not user_data.get("uuid"):
        user_data["uuid"] = payload["uuid"]
    if payload.get("username") and not user_data.get("username"):
        user_data["username"] = payload["username"]
    if payload.get("system_id") not in (None, "") and user_data.get("id") is None:
        user_data["id"] = int(payload["system_id"])
    if payload.get("telegram_id") not in (None, "") and user_data.get("telegramId") is None:
        user_data["telegramId"] = str(payload["telegram_id"])
    return user_data


async def _analyze_event(
    container: APIContainer,
    user_data: dict[str, Any],
    payload: dict[str, Any],
    rules: dict[str, Any],
) -> DecisionBundle:
    async def get_manual_override(target_ip: str) -> Optional[str]:
        manual_decision = await container.store.async_get_ip_override(target_ip)
        if manual_decision:
            return manual_decision
        return await container.analysis_store.get_unsure_pattern(target_ip)

    behavior_engine = BehavioralEngine(container.analysis_store, rules)

    async def analyze_behavior(current_uuid: str, target_ip: str, current_tag: str) -> dict[str, Any]:
        result = await behavior_engine.analyze(current_uuid, target_ip, current_tag)
        result["subnet"] = container.analysis_store.get_subnet(target_ip)
        return result

    def record_stats(asn: Optional[int], status: str, matched_kw: Optional[str], org: str) -> None:
        # Daily/stat buffers are not part of the panel control-plane contract in v1.
        return None

    bundle = await evaluate_mobile_network(
        context=ScoringContext(
            ip=str(payload["ip"]),
            uuid=str(user_data.get("uuid") or "") or None,
            tag=str(payload.get("tag") or "") or None,
        ),
        config=rules,
        deps=ScoringDependencies(
            get_manual_override=get_manual_override,
            get_ip_info=ipinfo_api.get_ip_info,
            parse_asn=ipinfo_api.parse_asn,
            normalize_isp_name=ipinfo_api.normalize_isp_name,
            is_datacenter=ipinfo_api.is_datacenter,
            analyze_behavior=analyze_behavior,
            get_promoted_pattern=container.store.async_get_promoted_pattern,
            get_legacy_confidence=container.analysis_store.get_learning_confidence,
            check_ip_api_mobile=lambda _: asyncio.sleep(0, result=None),
            record_decision=behavior_engine.record_decision,
            record_stats=record_stats,
        ),
    )
    return bundle


async def _apply_enforcement_if_needed(
    container: APIContainer,
    client: PanelClient,
    user_data: dict[str, Any],
    payload: dict[str, Any],
    bundle: DecisionBundle,
    rules: dict[str, Any],
) -> Optional[dict[str, Any]]:
    settings = rules.get("settings", {})
    if bundle.verdict != "HOME" or bundle.confidence_band not in {"HIGH_HOME", "PROBABLE_HOME"}:
        return None
    uuid = str(user_data.get("uuid") or "").strip()
    if not uuid:
        return None

    warning_only = (
        bool(settings.get("warning_only_mode", False))
        or bool(settings.get("shadow_mode", True))
        or should_warning_only(bundle)
        or not bundle.punitive_eligible
    )
    now = datetime.utcnow().replace(microsecond=0)
    row = await container.analysis_store.fetch_one(
        """
        SELECT strikes, warning_count
        FROM violations
        WHERE uuid = ?
        """,
        (uuid,),
    )
    strikes = int(row["strikes"]) if row and row["strikes"] is not None else 0
    warning_count = int(row["warning_count"]) if row and row["warning_count"] is not None else 0

    if warning_only:
        next_warning_count = warning_count + 1
        await container.analysis_store.execute(
            """
            INSERT INTO violations (
                uuid, strikes, unban_time, last_forgiven, last_strike_time,
                warning_time, warning_count, restriction_mode,
                saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, 'SQUAD', NULL, NULL, NULL)
            ON CONFLICT(uuid) DO UPDATE SET
                warning_time = excluded.warning_time,
                warning_count = excluded.warning_count,
                last_strike_time = excluded.last_strike_time
            """,
            (
                uuid,
                strikes,
                now.isoformat(),
                now.isoformat(),
                now.isoformat(),
                next_warning_count,
            ),
        )
        return {
            "type": "warning",
            "warning_count": next_warning_count,
            "warning_only": True,
        }

    durations = settings.get(
        "ban_durations_minutes",
        ENFORCEMENT_SETTINGS_DEFAULTS["ban_durations_minutes"],
    )
    if not isinstance(durations, list) or not durations:
        durations = ENFORCEMENT_SETTINGS_DEFAULTS["ban_durations_minutes"]
    next_strike = max(strikes, 0) + 1
    duration = int(durations[min(next_strike - 1, len(durations) - 1)])
    restriction_state = build_auto_restriction_state(user_data, settings)
    unban_time = now + timedelta(minutes=duration)
    await container.analysis_store.execute(
        """
        INSERT INTO violations (
            uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count,
            restriction_mode, saved_traffic_limit_bytes, saved_traffic_limit_strategy, applied_traffic_limit_bytes
        ) VALUES (?, ?, ?, ?, ?, NULL, 0, ?, ?, ?, ?)
        ON CONFLICT(uuid) DO UPDATE SET
            strikes = excluded.strikes,
            unban_time = excluded.unban_time,
            last_forgiven = excluded.last_forgiven,
            last_strike_time = excluded.last_strike_time,
            warning_time = NULL,
            warning_count = 0,
            restriction_mode = excluded.restriction_mode,
            saved_traffic_limit_bytes = excluded.saved_traffic_limit_bytes,
            saved_traffic_limit_strategy = excluded.saved_traffic_limit_strategy,
            applied_traffic_limit_bytes = excluded.applied_traffic_limit_bytes
        """,
        (
            uuid,
            next_strike,
            unban_time.isoformat(),
            now.isoformat(),
            now.isoformat(),
            restriction_state["restriction_mode"],
            restriction_state["saved_traffic_limit_bytes"],
            restriction_state["saved_traffic_limit_strategy"],
            restriction_state["applied_traffic_limit_bytes"],
        ),
    )
    await container.analysis_store.execute(
        """
        INSERT INTO violation_history (uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid,
            str(payload.get("ip") or ""),
            str(bundle.isp or ""),
            bundle.asn,
            str(payload.get("tag") or ""),
            next_strike,
            duration,
            now.isoformat(),
        ),
    )
    if bool(settings.get("dry_run", True)) or not client.enabled:
        return {
            "type": "ban",
            "strike": next_strike,
            "ban_minutes": duration,
            "remote_updated": False,
            "dry_run": True,
        }

    def _remote_apply() -> bool:
        if restriction_state["restriction_mode"] == "TRAFFIC_CAP":
            result = apply_remote_traffic_cap(
                client,
                uuid,
                user_data,
                int(settings.get("traffic_cap_increment_gb", ENFORCEMENT_SETTINGS_DEFAULTS["traffic_cap_increment_gb"])),
            )
            return bool(result["remote_updated"])
        return apply_remote_access_state(client, uuid, settings, restricted=True)

    remote_updated = await asyncio.to_thread(_remote_apply)
    return {
        "type": "ban",
        "strike": next_strike,
        "ban_minutes": duration,
        "remote_updated": bool(remote_updated),
        "dry_run": False,
    }


async def _process_module_event(
    container: APIContainer,
    module: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    rules_state = container.store.get_live_rules_state()
    rules = rules_state["rules"]
    raw_ip = str(payload.get("ip") or "").strip()
    if not raw_ip:
        raise ValueError("Raw event is missing ip")

    user_data = await _resolve_remote_user(container, _remnawave_client(container), payload)
    user_data["module_id"] = module["module_id"]
    user_data["module_name"] = module["module_name"]

    exempt_ids = {int(value) for value in rules.get("exempt_ids", [])}
    exempt_tg_ids = {int(value) for value in rules.get("exempt_tg_ids", [])}
    system_id = user_data.get("id")
    telegram_id = user_data.get("telegramId")
    if system_id is not None and int(system_id) in exempt_ids:
        return {"status": "skipped", "reason": "exempt_system_id"}
    if telegram_id not in (None, "") and int(telegram_id) in exempt_tg_ids:
        return {"status": "skipped", "reason": "exempt_telegram_id"}

    manual_override = await container.store.async_get_ip_override(raw_ip)
    cached = None
    if not manual_override:
        manual_override = await container.analysis_store.get_unsure_pattern(raw_ip)
    if not manual_override:
        cached = await container.analysis_store.get_cached_decision(raw_ip)

    if cached:
        bundle = DecisionBundle.from_cache_record(raw_ip, cached)
    else:
        bundle = await _analyze_event(container, user_data, payload, rules)
        await container.analysis_store.cache_decision(raw_ip, bundle.to_cache_payload())

    event_id = await container.store.async_record_analysis_event(
        user_data,
        raw_ip,
        str(payload.get("tag") or ""),
        bundle,
    )
    bundle.event_id = event_id

    review_case_id: Optional[int] = None
    review_reason = review_reason_for_bundle(bundle)
    if review_reason:
        review_case = await container.store.async_ensure_review_case(
            user_data,
            raw_ip,
            str(payload.get("tag") or ""),
            bundle,
            event_id,
            review_reason,
        )
        review_case_id = review_case.id
        bundle.case_id = review_case_id

    enforcement_result = await _apply_enforcement_if_needed(
        container,
        _remnawave_client(container),
        user_data,
        payload,
        bundle,
        rules,
    )
    return {
        "status": "processed",
        "event_id": event_id,
        "review_case_id": review_case_id,
        "bundle": bundle.to_dict(),
        "review_reason": review_reason,
        "enforcement": enforcement_result,
    }


def register_module(container: APIContainer, payload: dict[str, Any], token: str) -> dict[str, Any]:
    protocol_version = _require_protocol_version(str(payload.get("protocol_version", PROTOCOL_VERSION)))
    module = container.store.register_module(
        str(payload.get("module_id") or ""),
        token,
        module_name=str(payload.get("module_name") or ""),
        version=str(payload.get("version") or ""),
        protocol_version=protocol_version,
        metadata=dict(payload.get("metadata") or {}),
        config_revision_applied=int(payload.get("config_revision_applied") or 0),
        auto_create=_bool_env("MOBGUARD_MODULE_AUTO_REGISTER", True),
    )
    return {
        "protocol_version": protocol_version,
        "module": module,
        "config": get_module_config(container, module)["config"],
    }


def record_module_heartbeat(container: APIContainer, payload: dict[str, Any], token: str) -> dict[str, Any]:
    protocol_version = _require_protocol_version(str(payload.get("protocol_version", PROTOCOL_VERSION)))
    module = container.store.authenticate_module(str(payload.get("module_id") or ""), token)
    updated = container.store.record_module_heartbeat(
        module["module_id"],
        status=str(payload.get("status") or "online"),
        version=str(payload.get("version") or module.get("version") or ""),
        protocol_version=protocol_version,
        config_revision_applied=int(payload.get("config_revision_applied") or 0),
        details=dict(payload.get("details") or {}),
    )
    return {
        "protocol_version": protocol_version,
        "module": updated,
        "desired_config_revision": container.store.get_live_rules_state()["revision"],
    }


def get_module_config(container: APIContainer, module: dict[str, Any] | None) -> dict[str, Any]:
    rules_state = container.store.get_live_rules_state()
    settings = rules_state["rules"].get("settings", {})
    return {
        "config": {
            "protocol_version": PROTOCOL_VERSION,
            "config_revision": rules_state["revision"],
            "updated_at": rules_state["updated_at"],
            "rules": rules_state["rules"],
            "module_runtime": _module_runtime(settings),
        },
        "module": module,
    }


async def ingest_module_events(container: APIContainer, payload: dict[str, Any], token: str) -> dict[str, Any]:
    protocol_version = _require_protocol_version(str(payload.get("protocol_version", PROTOCOL_VERSION)))
    module = container.store.authenticate_module(str(payload.get("module_id") or ""), token)
    accepted = 0
    duplicates = 0
    processed = 0
    review_cases = 0
    results: list[dict[str, Any]] = []

    for raw_item in list(payload.get("items") or []):
        item = dict(raw_item)
        uid = _event_uid(module["module_id"], item)
        if not container.store.ingest_raw_event(
            module["module_id"],
            module["module_name"],
            uid,
            str(item.get("occurred_at") or ""),
            {**item, "event_uid": uid},
        ):
            duplicates += 1
            results.append({"event_uid": uid, "status": "duplicate"})
            continue

        accepted += 1
        processed_result = await _process_module_event(container, module, {**item, "event_uid": uid})
        await asyncio.to_thread(
            container.store.mark_raw_event_processed,
            uid,
            analysis_event_id=processed_result.get("event_id"),
            review_case_id=processed_result.get("review_case_id"),
        )
        processed += 1
        if processed_result.get("review_case_id"):
            review_cases += 1
        results.append({"event_uid": uid, **processed_result})

    return {
        "protocol_version": protocol_version,
        "module_id": module["module_id"],
        "accepted": accepted,
        "duplicates": duplicates,
        "processed": processed,
        "review_cases": review_cases,
        "config_revision": container.store.get_live_rules_state()["revision"],
        "results": results,
    }


def list_modules(container: APIContainer) -> dict[str, Any]:
    modules = container.store.list_modules()
    return {
        "items": modules,
        "count": len(modules),
    }
