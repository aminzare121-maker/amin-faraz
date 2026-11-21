#!/usr/bin/env python3
"""Read-only smoke test for an explicitly configured OpenAI-compatible model.

No model is bundled, downloaded, installed, or paid for by this script.
"responded" verifies API connectivity only, NOT factual accuracy or licensing.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

# No project files, customer data, or private source code are sent in this probe.
PROMPT = "این یک آزمایش اتصال است. لطفاً یک جمله کوتاه به زبان فارسی بنویس."
PERSIAN = re.compile(r"[\u0600-\u06ff]")


def validate_base_url(value: str) -> str:
    parsed = urlsplit(value.strip().rstrip("/"))
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("URL credentials, query and fragment are forbidden")
    if not parsed.hostname:
        raise ValueError("Model URL must contain a hostname")
    local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
        raise ValueError("Only HTTPS or loopback HTTP model endpoints are allowed")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid model port")
    if parsed.path.endswith("/chat/completions"):
        raise ValueError("Use API base URL, not /chat/completions URL")
    return value.strip().rstrip("/")


def probe_model(env=None, opener=None) -> dict:
    env = dict(os.environ if env is None else env)
    base_url = env.get("AMIN_MODEL_BASE_URL", "").strip()
    model = env.get("AMIN_MODEL_NAME", "").strip()
    if not base_url or not model:
        return {"configured": False, "responded": False, "persian_output": False,
                "status": "not_configured",
                "reason": "Model URL and model name have not both been configured",
                "claim": "No live model tested"}
    try:
        base_url = validate_base_url(base_url)
    except (ValueError, OverflowError):
        return {"configured": True, "responded": False, "persian_output": False,
                "status": "invalid_configuration", "claim": "No live model tested"}
    endpoint = base_url + "/chat/completions"
    body = json.dumps({
        "model": model, "temperature": 0.1, "max_tokens": 100,
        "messages": [{"role": "system", "content": "به فارسی کوتاه پاسخ بده."},
                     {"role": "user", "content": PROMPT}]
    }, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json",
               "Accept": "application/json",
               "User-Agent": "amin-ai-support/0.4"}
    key = env.get("AMIN_MODEL_API_KEY", "")
    if key:
        headers["Authorization"] = "Bearer " + key
    req = Request(endpoint, data=body, headers=headers, method="POST")
    if opener is None:
        opener = urlopen
    start = monotonic()
    try:
        with opener(req, timeout=15) as response:
            data = json.load(response)
        elapsed_ms = round((monotonic() - start) * 1000, 1)
        text = data["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            return {"configured": True, "responded": False,
                    "persian_output": False, "status": "empty_response",
                    "latency_ms": elapsed_ms, "claim": "Model not validated"}
        persian = bool(PERSIAN.search(text))
        return {"configured": True, "responded": True,
                "persian_output": persian,
                "status": "response_smoke_passed" if persian else "non_persian_response",
                "latency_ms": elapsed_ms,
                "claim": "API connectivity checked; model quality and commercial license NOT verified"}
    except HTTPError as exc:
        return {"configured": True, "responded": False, "persian_output": False,
                "status": "http_error", "http_status": exc.code,
                "claim": "Model not validated"}
    except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, IndexError):
        return {"configured": True, "responded": False, "persian_output": False,
                "status": "connection_or_response_error", "claim": "Model not validated"}


if __name__ == "__main__":
    result = probe_model()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "response_smoke_passed" else 1)
