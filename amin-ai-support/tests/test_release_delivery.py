"""Safe artifact references never imply software installed, even if comment says it did."""
import unittest

from direct_github_relay import validated_delivery


class ReleaseMetadataTests(unittest.TestCase):
    def test_signed_release_metadata_passes(self):
        data = validated_delivery({
            "environment": "android",
            "url": "https://github.com/owner/app/releases/download/v1/amin.apk",
            "sha256": "A"*64})
        self.assertEqual(data["sha256"], "a"*64)
        self.assertTrue(data["user_approval_required"])
        self.assertFalse(data["installed"])
        self.assertFalse(data["download_verified"])

    def test_unsafe_or_unverified_references_blocked(self):
        base = {"environment": "android",
                "url": "https://github.com/owner/app/releases/download/v1/amin.apk",
                "sha256": "a"*64}
        for url in ("http://github.com/owner/app/releases/download/v1/amin.apk",
                    "https://other.site/owner/app/releases/download/v1/amin.apk",
                    "https://github.com/owner/app/actions/runs/123",
                    "https://github.com/owner/app/releases/download/v1/a.apk?key=secret",
                    "https://github.com/owner/app/releases/download/v1/../other.apk"):
            self.assertIsNone(validated_delivery({**base, "url": url}))
        self.assertIsNone(validated_delivery({**base, "sha256": "not-a-hash"}))
        self.assertIsNone(validated_delivery({**base, "environment": "windows"}))
        self.assertIsNone(validated_delivery("https://github.com/owner/app"))


if __name__ == "__main__":
    unittest.main()
