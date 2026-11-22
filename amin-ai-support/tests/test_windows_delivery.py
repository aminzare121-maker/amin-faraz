"""Strict GitHub-only allowlist and hash-verified download without execution."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request
from windows_delivery import deliver, validate_release, verify_redirect


class FakeReply:
    status = 200
    def __init__(self, data):
        self.stream = io.BytesIO(data)
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, n): return self.stream.read(n)


class FakeOpener:
    def __init__(self, data):
        self.data = data
    def open(self, req: Request, timeout=25):
        return FakeReply(self.data)


class WindowsDeliveryTests(unittest.TestCase):
    URL = "https://github.com/owner/app/releases/download/v1/program.zip"
    def test_verified_file_is_transferred_not_executed(self):
        data = b"legitimate artifact test bytes"
        sha = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            result = deliver(self.URL, sha, Path(folder), FakeOpener(data))
            self.assertTrue(result["sha256_verified"])
            self.assertFalse(result["installed"])
            self.assertFalse(result["executed"])
            self.assertEqual((Path(folder) / "program.zip").read_bytes(), data)

    def test_wrong_digest_leaves_no_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "mismatch"):
                deliver(self.URL, "0"*64, Path(folder), FakeOpener(b"bad"))
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_untrusted_hosts_and_file_extensions_blocked(self):
        sha = "f"*64
        for url in (
            "http://github.com/owner/app/releases/download/v1/program.zip",
            "https://evil.com/owner/app/releases/download/v1/program.zip",
            "https://github.com/owner/app/releases/download/v1/program.sh",
            "https://github.com/owner/app/releases/download/v1/../program.exe",
            "https://github.com/owner/app/releases/download/v1/program.zip?x=1",
            "https://github.com/owner/app/releases/download/v1/%70rogram.zip"):
            with self.assertRaises(ValueError):
                validate_release(url, sha)
        with self.assertRaises(ValueError):
            verify_redirect("https://evil.example/artifact")


if __name__ == "__main__":
    unittest.main()
