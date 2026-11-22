"""Repo CI gates for a lightweight mobile voice that uses event-driven GitHub."""
from pathlib import Path
import unittest

from instant_issue_worker import build_reply

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "amin-ai-support/android-client"
JAVA = ANDROID / "app/src/main/java/com/amin/support/mobile"


class LightweightVoiceTests(unittest.TestCase):
    def test_installed_apk_has_no_large_offline_models(self):
        gradle = (ANDROID / "app/build.gradle").read_text("utf8")
        self.assertNotIn("vosk-android", gradle)
        self.assertNotIn("sherpa-onnx", gradle)
        for path in ANDROID.rglob("*"):
            if path.is_file() and path.suffix in (".onnx", ".pt", ".gguf", ".mdl"):
                self.fail("Bundled offline model violates lightweight mode: " + str(path))

    def test_voice_requires_permission_explicit_start_and_android_service(self):
        manifest = (ANDROID / "app/src/main/AndroidManifest.xml").read_text("utf8")
        source = (JAVA / "OnlinePersianVoice.java").read_text("utf8")
        activity = (JAVA / "MainActivity.java").read_text("utf8")
        self.assertIn("android.permission.RECORD_AUDIO", manifest)
        self.assertIn("SpeechRecognizer.createSpeechRecognizer", source)
        self.assertIn("EXTRA_PREFER_OFFLINE, false", source)
        self.assertIn('intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "fa-IR")', source)
        self.assertIn("private boolean awaitingReply", source)
        self.assertIn("pauseForBackground", source)
        self.assertIn("toggleOnlineVoice()", activity)
        self.assertIn("requestPermissions(", activity)
        self.assertIn("SpeechRecognizer", source)
        self.assertNotIn("Model(", source)

    def test_private_github_issue_does_not_claim_chatgpt_or_workflow_started(self):
        activity = (JAVA / "MainActivity.java").read_text("utf8")
        self.assertIn("اجرای GitHub Actions و دریافت پاسخ هنوز تأیید نشده", activity)
        self.assertIn("ثبت Issue به‌تنهایی به معنای اجرای GitHub Actions یا ChatGPT نیست", activity)
        self.assertNotIn("اکنون منتظر پاسخ عامل متصل به ChatGPT است", activity)

    def test_event_worker_has_registered_project_without_duplicate(self):
        worker = (ROOT / "amin-ai-support/instant_issue_worker.py").read_text("utf8")
        self.assertNotIn('config["projects"].append', worker)
        self.assertIn('item.get("id") == "support"', worker)

    def test_real_registered_support_can_answer_without_model(self):
        actual = build_reply("اتصال به GitHub چگونه است؟", "support", ROOT)
        self.assertIsInstance(actual["answer"], str)
        self.assertTrue(actual["answer"].strip())
        self.assertIn("needs_human", actual)
        self.assertIn("sources", actual)


if __name__ == "__main__":
    unittest.main()
