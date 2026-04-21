from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _int_setting(settings: dict[str, Any], key: str, default: int) -> int:
    value = settings.get(key, default)
    if value in (None, ""):
        return default
    return int(value)


def _float_setting(settings: dict[str, Any], key: str, default: float) -> float:
    value = settings.get(key, default)
    if value in (None, ""):
        return default
    return float(value)


def _bool_setting(settings: dict[str, Any], key: str, default: bool) -> bool:
    value = settings.get(key, default)
    if value in (None, ""):
        return default
    return bool(value)


@dataclass(frozen=True)
class ProviderProfile:
    key: str
    classification: str
    aliases: tuple[str, ...]
    mobile_markers: tuple[str, ...]
    home_markers: tuple[str, ...]
    asns: tuple[int, ...]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ProviderProfile":
        return cls(
            key=str(payload.get("key", "")).strip().lower(),
            classification=str(payload.get("classification", "mixed")).strip().lower(),
            aliases=tuple(str(item).lower() for item in payload.get("aliases", [])),
            mobile_markers=tuple(str(item).lower() for item in payload.get("mobile_markers", [])),
            home_markers=tuple(str(item).lower() for item in payload.get("home_markers", [])),
            asns=tuple(int(item) for item in payload.get("asns", [])),
        )


@dataclass(frozen=True)
class DetectionRules:
    pure_mobile_asns: tuple[int, ...]
    pure_home_asns: tuple[int, ...]
    mixed_asns: tuple[int, ...]
    allowed_isp_keywords: tuple[str, ...]
    home_isp_keywords: tuple[str, ...]
    exclude_isp_keywords: tuple[str, ...]
    provider_profiles: tuple[ProviderProfile, ...]

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "DetectionRules":
        return cls(
            pure_mobile_asns=tuple(int(item) for item in config.get("pure_mobile_asns", [])),
            pure_home_asns=tuple(int(item) for item in config.get("pure_home_asns", [])),
            mixed_asns=tuple(int(item) for item in config.get("mixed_asns", [])),
            allowed_isp_keywords=tuple(str(item).lower() for item in config.get("allowed_isp_keywords", [])),
            home_isp_keywords=tuple(str(item).lower() for item in config.get("home_isp_keywords", [])),
            exclude_isp_keywords=tuple(str(item).lower() for item in config.get("exclude_isp_keywords", [])),
            provider_profiles=tuple(
                ProviderProfile.from_payload(item)
                for item in config.get("provider_profiles", [])
                if isinstance(item, dict)
            ),
        )


@dataclass(frozen=True)
class ScoreWeights:
    pure_asn_score: int
    mixed_asn_score: int
    ptr_home_penalty: int
    mobile_kw_bonus: int
    provider_mobile_marker_bonus: int
    provider_home_marker_penalty: int
    ip_api_mobile_bonus: int
    pure_home_asn_penalty: int
    score_subnet_mobile_bonus: int
    score_subnet_home_penalty: int
    score_churn_high_bonus: int
    score_churn_medium_bonus: int
    score_stationary_penalty: int

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ScoreWeights":
        settings = config.get("settings", {})
        return cls(
            pure_asn_score=_int_setting(settings, "pure_asn_score", 60),
            mixed_asn_score=_int_setting(settings, "mixed_asn_score", 45),
            ptr_home_penalty=_int_setting(settings, "ptr_home_penalty", -20),
            mobile_kw_bonus=_int_setting(settings, "mobile_kw_bonus", 20),
            provider_mobile_marker_bonus=_int_setting(settings, "provider_mobile_marker_bonus", 18),
            provider_home_marker_penalty=_int_setting(settings, "provider_home_marker_penalty", -18),
            ip_api_mobile_bonus=_int_setting(settings, "ip_api_mobile_bonus", 30),
            pure_home_asn_penalty=_int_setting(settings, "pure_home_asn_penalty", -100),
            score_subnet_mobile_bonus=_int_setting(settings, "score_subnet_mobile_bonus", 40),
            score_subnet_home_penalty=_int_setting(settings, "score_subnet_home_penalty", 0),
            score_churn_high_bonus=_int_setting(settings, "score_churn_high_bonus", 30),
            score_churn_medium_bonus=_int_setting(settings, "score_churn_medium_bonus", 15),
            score_stationary_penalty=_int_setting(settings, "score_stationary_penalty", -5),
        )


@dataclass(frozen=True)
class Thresholds:
    threshold_probable_home: int
    threshold_probable_mobile: int
    threshold_home: int
    threshold_mobile: int
    auto_enforce_requires_hard_or_multi_signal: bool
    probable_home_warning_only: bool
    provider_conflict_review_only: bool

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Thresholds":
        settings = config.get("settings", {})
        return cls(
            threshold_probable_home=_int_setting(settings, "threshold_probable_home", 30),
            threshold_probable_mobile=_int_setting(settings, "threshold_probable_mobile", 50),
            threshold_home=_int_setting(settings, "threshold_home", 15),
            threshold_mobile=_int_setting(settings, "threshold_mobile", 60),
            auto_enforce_requires_hard_or_multi_signal=_bool_setting(
                settings,
                "auto_enforce_requires_hard_or_multi_signal",
                True,
            ),
            probable_home_warning_only=_bool_setting(settings, "probable_home_warning_only", True),
            provider_conflict_review_only=_bool_setting(settings, "provider_conflict_review_only", True),
        )


@dataclass(frozen=True)
class LearningThresholds:
    learning_promote_asn_min_support: int
    learning_promote_asn_min_precision: float
    learning_promote_combo_min_support: int
    learning_promote_combo_min_precision: float

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "LearningThresholds":
        settings = config.get("settings", {})
        return cls(
            learning_promote_asn_min_support=_int_setting(settings, "learning_promote_asn_min_support", 10),
            learning_promote_asn_min_precision=_float_setting(settings, "learning_promote_asn_min_precision", 0.95),
            learning_promote_combo_min_support=_int_setting(settings, "learning_promote_combo_min_support", 5),
            learning_promote_combo_min_precision=_float_setting(settings, "learning_promote_combo_min_precision", 0.9),
        )


@dataclass(frozen=True)
class RuntimeRuleView:
    detection: DetectionRules
    weights: ScoreWeights
    thresholds: Thresholds
    learning: LearningThresholds

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RuntimeRuleView":
        return cls(
            detection=DetectionRules.from_config(config),
            weights=ScoreWeights.from_config(config),
            thresholds=Thresholds.from_config(config),
            learning=LearningThresholds.from_config(config),
        )
