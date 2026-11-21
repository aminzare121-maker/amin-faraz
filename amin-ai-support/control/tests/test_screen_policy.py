"""Policy checks only: these are not Android runtime/device tests."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / "control"
ANDROID = ROOT / "android-companion"


class AndroidScreenPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((CONTROL / "screen_policy.json").read_text(encoding="utf-8"))
        self.native = (ANDROID / "ScreenAwakeSession.kt").read_text(encoding="utf-8")
        self.docs = (ANDROID / "README_FA.md").read_text(encoding="utf-8")

    def test_owner_requested_rewake_kept_as_open_requirement(self):
        self.assertIn("مجدداً روشن", self.policy["owner_requested_behavior_fa"])
        self.assertEqual(
            self.policy["implementation"]["automatically_wake_after_all_screen_off_events"],
            "not_implemented",
        )
        self.assertFalse(self.policy["native_android_companion_installed"])
        self.assertFalse(self.policy["verified_on_physical_device"])

    def test_screen_management_requires_foreground_active_task_and_opt_in(self):
        self.assertTrue(self.policy["user_opt_in_required"])
        self.assertIn("isJavabTaskActive && ownerOptedIn && isForeground", self.native)
        self.assertIn("FLAG_KEEP_SCREEN_ON", self.native)
        self.assertIn("activity.setTurnScreenOn(true)", self.native)
        self.assertIn("activity.setTurnScreenOn(false)", self.native)
        self.assertIn("activity.window.clearFlags(", self.native)

    def test_no_background_wakeup_or_lockscreen_bypass_claimed(self):
        self.assertEqual(self.policy["implementation"]["force_screen_after_power_button"],
                         "not_implemented")
        self.assertEqual(self.policy["implementation"]["bypass_lockscreen"],
                         "prohibited")
        self.assertNotIn("ACQUIRE_CAUSES_WAKEUP", self.native)
        self.assertNotIn("DISABLE_KEYGUARD", self.native)
        self.assertIn("APK", self.docs)
        self.assertIn("آزمایش نشده", self.docs)

    def test_only_owner_visible_requirement_not_confused_with_product_success(self):
        contract = (ROOT / "OWNER_REQUIREMENTS_FA.md").read_text(encoding="utf-8")
        javab = (CONTROL / "JAVAB_README_FA.md").read_text(encoding="utf-8")
        self.assertIn("صفحه گوشی", contract)
        self.assertIn("screen_policy.json", javab)
        self.assertIn("هنوز", javab)


if __name__ == "__main__":
    unittest.main()
