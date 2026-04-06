from __future__ import annotations

from .models import DecisionBundle


def derive_punitive_eligibility(bundle: DecisionBundle) -> bool:
    if bundle.verdict != "HOME":
        return False
    if bundle.confidence_band != "HIGH_HOME":
        return False
    if bundle.has_hard_home_reason:
        return True
    return len(bundle.home_sources) >= 2


def review_reason_for_bundle(bundle: DecisionBundle) -> str | None:
    if bundle.verdict == "UNSURE" or bundle.confidence_band == "UNSURE":
        return "unsure"
    if bundle.confidence_band == "PROBABLE_HOME":
        return "probable_home"
    if bundle.verdict == "HOME" and bundle.confidence_band == "HIGH_HOME" and not bundle.punitive_eligible:
        return "home_requires_review"
    return None


def should_warning_only(bundle: DecisionBundle) -> bool:
    return bundle.verdict == "HOME" and bundle.confidence_band == "PROBABLE_HOME"
