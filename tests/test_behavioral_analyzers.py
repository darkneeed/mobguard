import asyncio
import unittest

from behavioral_analyzers import BehavioralEngine


class _FakeAnalysisDb:
    def __init__(self, history_rows):
        self.history_rows = history_rows
        self.updated_history = []
        self.updated_sessions = []

    async def count_concurrent_users(self, ip, minutes=15):
        return 0

    async def get_churn_rate(self, uuid, hours):
        return 0

    async def get_recent_ip_history(self, uuid, days, limit=1000):
        return list(self.history_rows)

    async def get_session_lifetime(self, uuid, ip):
        return 0.0

    async def get_subnet_evidence(self, ip):
        return {"MOBILE": 0, "HOME": 0}

    async def update_ip_history(self, uuid, ip):
        self.updated_history.append((uuid, ip))

    async def update_session(self, uuid, ip, tag):
        self.updated_sessions.append((uuid, ip, tag))

    async def record_subnet_signal(self, ip, uuid, signal_type):
        return None

    def get_subnet(self, ip):
        return ip.rsplit(".", 1)[0]


BASE_CONFIG = {
    "settings": {
        "concurrency_threshold": 2,
        "churn_window_hours": 6,
        "churn_mobile_threshold": 3,
        "score_churn_high_bonus": 30,
        "score_churn_medium_bonus": 15,
        "history_lookback_days": 14,
        "history_min_gap_minutes": 30,
        "history_mobile_same_subnet_min_distinct_ips": 8,
        "history_mobile_bonus": 40,
        "history_home_same_ip_min_records": 5,
        "history_home_same_ip_min_span_hours": 24,
        "history_home_penalty": -25,
        "lifetime_stationary_hours": 12,
        "score_stationary_penalty": -5,
        "score_subnet_mobile_bonus": 40,
        "score_subnet_home_penalty": 0,
        "subnet_mobile_min_evidence": 1,
        "subnet_home_min_evidence": 3,
    }
}


class BehavioralAnalyzersTests(unittest.TestCase):
    def test_none_settings_fall_back_to_defaults(self):
        db = _FakeAnalysisDb([])
        config = {
            "settings": {
                "concurrency_threshold": None,
                "churn_window_hours": None,
                "churn_mobile_threshold": None,
                "score_churn_high_bonus": None,
                "score_churn_medium_bonus": None,
                "history_lookback_days": None,
                "history_min_gap_minutes": None,
                "history_mobile_same_subnet_min_distinct_ips": None,
                "history_mobile_bonus": None,
                "history_home_same_ip_min_records": None,
                "history_home_same_ip_min_span_hours": None,
                "history_home_penalty": None,
                "lifetime_stationary_hours": None,
                "score_stationary_penalty": None,
                "score_subnet_mobile_bonus": None,
                "score_subnet_home_penalty": None,
                "subnet_mobile_min_evidence": None,
                "subnet_home_min_evidence": None,
            }
        }
        engine = BehavioralEngine(db, config)

        result = asyncio.run(engine.analyze("uuid-fallback", "1.2.3.4", "TAG", persist_state=False))

        self.assertEqual(result["total_behavior_score"], 0)
        self.assertFalse(result["concurrency_immunity"])

    def test_history_mobile_signal_ignores_short_gap_duplicates(self):
        db = _FakeAnalysisDb(
            [
                {"ip": "188.120.1.1", "timestamp": "2026-04-01T00:00:00"},
                {"ip": "188.120.1.1", "timestamp": "2026-04-01T00:05:00"},
                {"ip": "188.120.1.2", "timestamp": "2026-04-01T00:40:00"},
                {"ip": "188.120.1.3", "timestamp": "2026-04-01T01:20:00"},
                {"ip": "188.120.1.4", "timestamp": "2026-04-01T02:00:00"},
                {"ip": "188.120.1.5", "timestamp": "2026-04-01T02:40:00"},
                {"ip": "188.120.1.6", "timestamp": "2026-04-01T03:20:00"},
                {"ip": "188.120.1.7", "timestamp": "2026-04-01T04:00:00"},
                {"ip": "188.120.1.8", "timestamp": "2026-04-01T04:40:00"},
            ]
        )
        engine = BehavioralEngine(db, BASE_CONFIG)

        result = asyncio.run(engine.analyze("uuid-1", "188.120.1.99", "TAG", persist_state=False))

        self.assertEqual(result["history_mobile_bonus"], 40)
        self.assertEqual(result["history_summary"]["top_subnet_distinct_ips"], 8)
        self.assertEqual(result["history_summary"]["spaced_samples"], 8)
        self.assertEqual(db.updated_history, [])
        self.assertEqual(db.updated_sessions, [])

    def test_history_home_signal_detects_stable_same_ip_across_days(self):
        db = _FakeAnalysisDb(
            [
                {"ip": "91.200.10.10", "timestamp": "2026-04-01T00:00:00"},
                {"ip": "91.200.10.10", "timestamp": "2026-04-01T12:00:00"},
                {"ip": "91.200.10.10", "timestamp": "2026-04-02T00:00:00"},
                {"ip": "91.200.10.10", "timestamp": "2026-04-02T12:00:00"},
                {"ip": "91.200.10.10", "timestamp": "2026-04-03T00:00:00"},
            ]
        )
        engine = BehavioralEngine(db, BASE_CONFIG)

        result = asyncio.run(engine.analyze("uuid-2", "91.200.10.10", "TAG"))

        self.assertEqual(result["history_home_penalty"], -25)
        self.assertGreaterEqual(result["history_summary"]["top_same_ip_span_hours"], 48)
        self.assertEqual(db.updated_history, [("uuid-2", "91.200.10.10")])
        self.assertEqual(db.updated_sessions, [("uuid-2", "91.200.10.10", "TAG")])


if __name__ == "__main__":
    unittest.main()
