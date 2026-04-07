import os
import json
import shutil
import tempfile
import unittest

from mobguard_platform.models import DecisionBundle
from mobguard_platform.store import PlatformStore


class StoreReviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-store-")
        self.db_path = os.path.join(self.temp_dir, "test.sqlite3")
        self.config_path = os.path.join(self.temp_dir, "config.json")
        self.base_config = {
            "mixed_asns": [12345],
            "allowed_isp_keywords": ["mobile"],
            "home_isp_keywords": ["fiber"],
            "exclude_isp_keywords": ["hosting"],
            "admin_tg_ids": [1001],
            "settings": {
                "threshold_mobile": 60,
                "threshold_home": 15,
                "threshold_probable_home": 30,
                "threshold_probable_mobile": 50,
                "learning_promote_asn_min_support": 1,
                "learning_promote_asn_min_precision": 1.0,
                "learning_promote_combo_min_support": 1,
                "learning_promote_combo_min_precision": 1.0,
                "shadow_mode": True,
            },
        }
        self.store = PlatformStore(self.db_path, self.base_config, self.config_path)
        self.store.init_schema()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_review_roundtrip_creates_override_and_pattern(self):
        bundle = DecisionBundle(
            ip="10.10.10.10",
            verdict="HOME",
            confidence_band="PROBABLE_HOME",
            score=18,
            asn=12345,
            isp="ISP",
        )
        bundle.add_reason(
            "keyword_home",
            "keyword",
            -20,
            "soft",
            "HOME",
            "keyword matched",
            {"keywords": ["fiber"]},
        )
        user = {"uuid": "uuid-1", "username": "alice", "telegramId": "1001"}
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, "probable_home")
        resolved = self.store.resolve_review_case(summary.id, "HOME", "admin", 1001, "confirmed")

        self.assertEqual(resolved["status"], "RESOLVED")
        self.assertEqual(self.store.get_ip_override(bundle.ip), "HOME")
        pattern = self.store.get_promoted_pattern("asn", "12345")
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern["decision"], "HOME")

    def test_live_rules_revision_conflict_is_rejected(self):
        state = self.store.get_live_rules_state()
        updated = self.store.update_live_rules(
            {"settings": {"threshold_mobile": 70}},
            "admin",
            1001,
            expected_revision=state["revision"],
            expected_updated_at=state["updated_at"],
        )
        self.assertEqual(updated["revision"], state["revision"] + 1)

        with self.assertRaises(ValueError):
            self.store.update_live_rules(
                {"settings": {"threshold_mobile": 80}},
                "admin",
                1001,
                expected_revision=state["revision"],
                expected_updated_at=state["updated_at"],
            )

        with open(self.config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["settings"]["threshold_mobile"], 70)
        self.assertEqual(payload["_meta"]["revision"], updated["revision"])

    def test_health_snapshot_reflects_core_heartbeat(self):
        previous = os.environ.get("IPINFO_TOKEN")
        os.environ["IPINFO_TOKEN"] = "test-token"
        try:
            self.store.update_service_heartbeat("mobguard-core", "ok", {"shadow_mode": True})
            snapshot = self.store.get_health_snapshot()
            self.assertEqual(snapshot["status"], "ok")
            self.assertTrue(snapshot["core"]["healthy"])
            self.assertTrue(snapshot["ipinfo_token_present"])
        finally:
            if previous is None:
                os.environ.pop("IPINFO_TOKEN", None)
            else:
                os.environ["IPINFO_TOKEN"] = previous

    def test_health_snapshot_degrades_without_ipinfo_token(self):
        previous = os.environ.pop("IPINFO_TOKEN", None)
        try:
            self.store.update_service_heartbeat("mobguard-core", "ok", {"shadow_mode": True})
            snapshot = self.store.get_health_snapshot()
            self.assertEqual(snapshot["status"], "degraded")
            self.assertFalse(snapshot["ipinfo_token_present"])
        finally:
            if previous is not None:
                os.environ["IPINFO_TOKEN"] = previous


if __name__ == "__main__":
    unittest.main()
