#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot GitHub CLI credential adapter for the EXISTING Amin bridge0.2.

This does not create a new bridge, poll continuously, or execute shell requests
from GitHub. A locally authorized gh session supplies a temporary token to
the already-reviewed local_once_host.run_once(). The token is never printed,
written to a file, or passed as a command-line argument.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import local_once_host as host

# Frozen SHA-256 values from PR41's reviewed bridge and launcher.
BRIDGE_SHA256 = "869aeb5bd469223d2b58502ecc4ebd2b17441708476df29ee574f5639fec72b6"
LAUNCHER_SHA256 = "cde1247a6f5f8cfe79878877d3ead0c951dc8e4e1c206304f718fd93f34105f2"


def _authenticated_cli_token():
    """Return a local-only token or a non-secret status message."""
    gh = shutil.which("gh")
    if not gh:
        return None, "GH_CLI_MISSING"
    try:
        status = subprocess.run(
            [gh, "auth", "status", "--hostname", "github.com"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=20, check=False,
        )
        if status.returncode:
            return None, "GH_LOGIN_REQUIRED"
        result = subprocess.run(
            [gh, "auth", "token", "--hostname", "github.com"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=20, check=False,
        )
        raw = result.stdout.strip()
        if result.returncode or not raw or len(raw) > 1000 or any(b <= 32 for b in raw):
            return None, "GH_TOKEN_NOT_AVAILABLE"
        return raw.decode("ascii"), None
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None, "GH_CLI_UNAVAILABLE"


def main():
    token, blocker = _authenticated_cli_token()
    if blocker:
        print(json.dumps({"status": blocker, "connected": False}))
        if blocker == "GH_LOGIN_REQUIRED":
            print("Use official gh auth login --web in a LOCAL interactive Windows terminal; approve in your own browser.")
        elif blocker == "GH_CLI_MISSING":
            print("GitHub CLI is not installed. Ask the owner before installing GitHub CLI.")
        return 2

    original_cached_auth = host.cached_auth
    try:
        # Only the trusted one-shot local host receives the credential in memory.
        host.cached_auth = lambda: token
        outcome = host.run_once(BRIDGE_SHA256, LAUNCHER_SHA256)
        safe = {
            "status": outcome.get("status", "UNKNOWN"),
            "live_bridge_executed": outcome.get("live_bridge_executed", False),
            "returncode": outcome.get("returncode"),
            "handshake_verified_by_host": False,
            "verification": "CHECK_REAL_AMIN-WIN-RESULT-v1_IN_ISSUE38",
        }
        print(json.dumps(safe, sort_keys=True))
        # Status only: a successful child exit is not proof of GitHub delivery.
        return 0 if outcome.get("returncode") == 0 else 1
    finally:
        host.cached_auth = original_cached_auth
        token = None


if __name__ == "__main__":
    raise SystemExit(main())
