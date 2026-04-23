from __future__ import annotations

from typing import Any

from mobguard_platform.runtime_admin_defaults import ENFORCEMENT_SETTINGS_DEFAULTS

from ..context import APIContainer
from .runtime_state import load_runtime_config


def build_automation_status(container: APIContainer) -> dict[str, Any]:
    runtime_config = load_runtime_config(container)
    runtime_settings = runtime_config.get("settings", {}) if isinstance(runtime_config, dict) else {}
    store = getattr(container, "store", None)
    if store is not None and hasattr(store, "get_live_rules_state"):
        live_rules = store.get_live_rules_state().get("rules", {})
    else:
        live_rules = {}
    detection_settings = live_rules.get("settings", {}) if isinstance(live_rules.get("settings"), dict) else {}

    flags = {
        "dry_run": bool(runtime_settings.get("dry_run", ENFORCEMENT_SETTINGS_DEFAULTS["dry_run"])),
        "warning_only_mode": bool(
            runtime_settings.get("warning_only_mode", ENFORCEMENT_SETTINGS_DEFAULTS["warning_only_mode"])
        ),
        "manual_review_mixed_home_enabled": bool(
            runtime_settings.get(
                "manual_review_mixed_home_enabled",
                ENFORCEMENT_SETTINGS_DEFAULTS["manual_review_mixed_home_enabled"],
            )
        ),
        "manual_ban_approval_enabled": bool(
            runtime_settings.get(
                "manual_ban_approval_enabled",
                ENFORCEMENT_SETTINGS_DEFAULTS["manual_ban_approval_enabled"],
            )
        ),
        "shadow_mode": bool(detection_settings.get("shadow_mode", True)),
        "auto_enforce_requires_hard_or_multi_signal": bool(
            detection_settings.get("auto_enforce_requires_hard_or_multi_signal", True)
        ),
        "provider_conflict_review_only": bool(detection_settings.get("provider_conflict_review_only", True)),
    }

    mode_reasons: list[str] = []
    if flags["dry_run"]:
        mode_reasons.append("dry_run")
    if flags["shadow_mode"]:
        mode_reasons.append("shadow_mode")
    if flags["warning_only_mode"]:
        mode_reasons.append("warning_only_mode")

    if flags["dry_run"] or flags["shadow_mode"]:
        mode = "observe"
    elif flags["warning_only_mode"]:
        mode = "warning_only"
    else:
        mode = "enforce"

    return {
        "mode": mode,
        "mode_reasons": mode_reasons,
        "flags": flags,
    }
