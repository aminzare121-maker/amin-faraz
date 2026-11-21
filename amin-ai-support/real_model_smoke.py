#!/usr/bin/env python3
"""End-to-end test using an ACTUALLY RUNNING local LLM.

This is a limited, synthetic-fact test with a real model (not a mocked server).
Neither a passing probe nor this fact question establishes product readiness.
Requires an explicitly configured OpenAI-compatible model API.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import re

from amin_support import SupportEngine
from model_probe import probe_model, validate_base_url


def run():
    base = os.environ.get("AMIN_MODEL_BASE_URL", "")
    model = os.environ.get("AMIN_MODEL_NAME", "")
    if not base or not model:
        return {"status": "not_configured", "live_model": False,
                "end_to_end_passed": False}
    try:
        checked = validate_base_url(base)
    except (ValueError, OverflowError):
        return {"status": "invalid_endpoint", "live_model": False,
                "end_to_end_passed": False}

    # The pilot must run only against a local process. No customer data is sent.
    if urlsplit(checked).hostname not in ("127.0.0.1", "localhost", "::1"):
        return {"status": "local_only_pilot", "live_model": False,
                "end_to_end_passed": False}
    probe = probe_model()
    result = {"model": model,
              "live_model": probe.get("responded", False),
              "persian_output": probe.get("persian_output", False),
              "probe_status": probe["status"],
              "probe_latency_ms": probe.get("latency_ms"),
              "end_to_end_passed": False}
    if not probe.get("responded"):
        result["status"] = "model_probe_failed"
        return result
    try:
        with tempfile.TemporaryDirectory(prefix="amin-real-model-") as temp:
            root = Path(temp)
            source = root / "docs"
            source.mkdir()
            (source / "README.md").write_text(
                "راهنمای تست فرضی: پورت سرویس آزمایشی 8765 است. "
                "اگر اتصال رد شد، ابتدا سرویس پورت 8765 را بررسی کنید. "
                "این متن فقط برای آزمون است و اطلاعات هیچ برنامه واقعی را توصیف نمی‌کند.",
                encoding="utf-8",
            )
            config = root / "projects.json"
            config.write_text(json.dumps({"projects": [
                {"id": "trial", "name": "پروژه آزمایشی محلی",
                 "source_prefixes": ["README.md"],
                 "public_paths": ["README.md"]}
            ]}, ensure_ascii=False), encoding="utf-8")
            engine = SupportEngine(config, root / "trial.sqlite3")
            engine.knowledge.ingest(engine.projects["trial"], source)
            # Inspect a real model answer against the same toy evidence. Only
            # a synthetic public sentence can appear in CI logs, never user data.
            raw_request = Request(
                checked + "/chat/completions",
                data=json.dumps({
                    "model": model, "temperature": 0.1, "max_tokens": 110,
                    "messages": [
                        {"role": "system", "content": "از سند [1] استفاده کن. پاسخ کوتاه و فارسی، با ارجاع [1]."},
                        {"role": "user", "content": "شواهد [1]: پورت سرویس آزمایشی 8765 است. شماره پورت چیست؟"}
                    ]}, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(raw_request, timeout=45) as remote_response:
                raw = json.load(remote_response)["choices"][0]["message"]["content"]
            result["raw_model_sample"] = str(raw)[:450]
            result["raw_sample_cited"] = bool(re.search(r"\[1\]", str(raw)))
            start = monotonic()
            answer = engine.answer("trial", "طبق راهنمای پروژه آزمایشی، شماره پورت سرویس چیست؟")
            result["query_latency_ms"] = round((monotonic() - start) * 1000, 1)
            result["grounded_answer"] = answer["answer"][:550]
            result["grounded_sources"] = answer["sources"]
            result["accepted_model_answer"] = answer["model_used"]
            result["correct_fact_in_answer"] = "8765" in answer["answer"]
            result["source_valid"] = any(
                item["path"] == "README.md" for item in answer["sources"])
            result["end_to_end_passed"] = bool(
                answer["model_used"] and result["correct_fact_in_answer"]
                and result["source_valid"] and probe.get("persian_output"))
            result["status"] = ("single_fact_grounding_passed"
                                if result["end_to_end_passed"]
                                else "live_model_ran_but_grounding_not_accepted")
    except Exception as exc:
        result["status"] = "inference_error"
        result["error_type"] = type(exc).__name__
        result["end_to_end_passed"] = False
    return result


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    sys.exit(0 if result["end_to_end_passed"] else 1)
