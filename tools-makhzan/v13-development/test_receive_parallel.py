import hashlib
import re
import tempfile
import unittest
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import Mock

from receive_parallel import receive


@contextmanager
def serve(payload, mode):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            start, end = map(int, re.fullmatch(r"bytes=(\d+)-(\d+)", self.headers["Range"]).groups())
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
            if mode != "untagged":
                changed = self.headers.get("If-Match") and mode == "changed"
                self.send_header("ETag", '"second"' if changed else '"first"')
            self.end_headers()
            try:
                self.wfile.write(payload[start:end+1])
            except (ConnectionResetError, BrokenPipeError):
                pass

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/movie"
        finally:
            server.shutdown()
            thread.join()


class ReceiverTests(unittest.TestCase):
    payload = b"0000ftyp" + bytes(range(256)) * 34000
    engine = SimpleNamespace(_allowed_https=lambda url: None,
                             SourceRedirectSafe=urllib.request.HTTPRedirectHandler, MAX_BYTES=600 << 20)

    def test_reassembles_all_bytes(self):
        with tempfile.TemporaryDirectory() as temp, serve(self.payload, "valid") as url:
            path = Path(temp) / "video.mp4"
            result = receive(url, path, self.engine, None)
            self.assertEqual(result, (len(self.payload), hashlib.sha256(self.payload).hexdigest()))
            self.assertEqual(path.read_bytes(), self.payload)

    def test_changed_version_removes_partial(self):
        with tempfile.TemporaryDirectory() as temp, serve(self.payload, "changed") as url:
            path = Path(temp) / "video.mp4"
            with self.assertRaisesRegex(ValueError, "version"):
                receive(url, path, self.engine, None)
            self.assertFalse(path.exists())

    def test_no_strong_etag_uses_original_receiver(self):
        with tempfile.TemporaryDirectory() as temp, serve(self.payload, "untagged") as url:
            path = Path(temp) / "video.mp4"
            fallback = Mock(return_value=(123, "test"))
            self.assertEqual(receive(url, path, self.engine, fallback), (123, "test"))
            fallback.assert_called_once_with(url, path)
