"""Owner safety mode: block external model calls until owner explicitly opts out.

A public cloud endpoint could be paid even if its trial quota is free. Default
to local-only model inference. This DOES NOT prevent other billing charges.
"""
from __future__ import annotations
import os
from urllib.parse import urlsplit

FALSE_VALUES = {"0", "false", "off", "no"}


def zero_payment_enabled(env=None) -> bool:
    values = os.environ if env is None else env
    return str(values.get("AMIN_ZERO_PAYMENT_MODE", "on")).strip().lower() not in FALSE_VALUES


def permits_model_url(url: str, env=None) -> bool:
    if not zero_payment_enabled(env):
        return True
    return urlsplit(url).hostname in {"127.0.0.1", "localhost", "::1"}
