#!/usr/bin/env python3
"""Download a declared release artifact to the user-selected Windows folder.

The checksum protects against accidental substitution/corruption. It does
NOT prove the publisher is safe. Never auto-runs installers or extracted files.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPRedirectHandler, Request

RELEASE = re.compile(
    r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/releases/download/"
    r"[A-Za-z0-9_.-]+/([A-Za-z0-9_.-]+\.(?:zip|msi|msix|exe))\Z", re.I)
HASH = re.compile(r"[a-fA-F0-9]{64}\Z")
HOSTS = {"release-assets.githubusercontent.com", "objects.githubusercontent.com"}
LIMIT = 250 * 1024 * 1024


def validate_release(url: str, sha: str):
    if not isinstance(url, str) or len(url) > 400 or not isinstance(sha, str):
        raise ValueError("Invalid artifact metadata")
    p = urlsplit(url)
    if (p.scheme != "https" or p.netloc != "github.com" or p.query or p.fragment
            or "%" in p.path or ".." in p.path or not HASH.fullmatch(sha)):
        raise ValueError("Only a hash-verified GitHub release URL is supported")
    matched = RELEASE.fullmatch(p.path)
    if not matched:
        raise ValueError("Only Windows release artifacts (ZIP/MSI/MSIX/EXE) are supported")
    return matched.group(1), sha.lower()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def verify_redirect(url: str):
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in HOSTS or p.username or p.password:
        raise ValueError("Untrusted GitHub redirect target")


def deliver(url: str, sha: str, folder: Path, opener=None):
    filename, expected = validate_release(url, sha)
    folder = Path(folder).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    if target.is_symlink():
        raise ValueError("Refusing to overwrite a symlink")
    if target.exists():
        raise FileExistsError("File exists: download under a new destination")
    opener = opener or build_opener(NoRedirect())
    tempfile_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".amin-verified-",
                                         suffix=".partial", delete=False) as output:
            tempfile_path = Path(output.name)
            digest = hashlib.sha256()
            next_url = url
            for attempt in range(5):
                req = Request(next_url, headers={"User-Agent": "AminVerifiedWindowsDelivery/0.1"})
                try:
                    response = opener.open(req, timeout=25)
                except HTTPError as error:
                    if error.code not in {301, 302, 303, 307, 308}:
                        raise RuntimeError("GitHub download failed with HTTP " + str(error.code)) from None
                    location = error.headers.get("Location")
                    if not location:
                        raise RuntimeError("Missing GitHub release redirect")
                    next_url = urljoin(next_url, location)
                    verify_redirect(next_url)
                    continue
                with response:
                    if response.status != 200:
                        raise RuntimeError("Unexpected artifact response status")
                    received = 0
                    while True:
                        chunk = response.read(32768)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > LIMIT:
                            raise ValueError("Artifact exceeds max permitted size")
                        digest.update(chunk)
                        output.write(chunk)
                break
            else:
                raise RuntimeError("Too many release redirects")
            output.flush()
            os.fsync(output.fileno())
        if digest.hexdigest() != expected:
            raise ValueError("SHA-256 mismatch: refusing delivery")
        os.replace(tempfile_path, target)
        return {"downloaded": True, "sha256_verified": True,
                "installed": False, "executed": False, "path": str(target)}
    finally:
        if tempfile_path and tempfile_path.exists():
            tempfile_path.unlink()


def main(argv=None):
    p = argparse.ArgumentParser(description="Amin verified Windows artifact delivery")
    p.add_argument("--url", required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--folder", type=Path, default=Path.home() / "Downloads" / "Amin AI")
    p.add_argument("--approve", action="store_true",
                   help="Explicitly allow downloading a new file, not executing it")
    args = p.parse_args(argv)
    validate_release(args.url, args.sha256)
    if not args.approve:
        print("Refused: --approve is required. Nothing downloaded.")
        return 2
    print(deliver(args.url, args.sha256, args.folder))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
