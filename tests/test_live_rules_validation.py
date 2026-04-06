import unittest

from mobguard_platform.store import validate_live_rules_patch


class LiveRulesValidationTests(unittest.TestCase):
    def test_valid_patch_normalizes_lists(self):
        payload = validate_live_rules_patch(
            {
                "mixed_asns": ["123", 456],
                "allowed_isp_keywords": ["mobile", "lte"],
                "settings": {"threshold_mobile": 70, "probable_home_warning_only": True},
            }
        )
        self.assertEqual(payload["mixed_asns"], [123, 456])
        self.assertEqual(payload["allowed_isp_keywords"], ["mobile", "lte"])
        self.assertTrue(payload["settings"]["probable_home_warning_only"])

    def test_invalid_setting_raises(self):
        with self.assertRaises(ValueError):
            validate_live_rules_patch({"settings": {"threshold_mobile": "high"}})


if __name__ == "__main__":
    unittest.main()
