"""Amin economic calendar evidence gate (offline, no trading)."""
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import math

def parse_time(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone missing")
    return dt.astimezone(timezone.utc)

def parse_number(value):
    if value is None or value == "":
        return None
    digits = str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    v = float(digits.replace("٫", ".").replace("−", "-").replace(",", ""))
    if not math.isfinite(v):
        raise ValueError("invalid value")
    return v

def assess(record, now_iso, max_age_minutes=120):
    now = parse_time(now_iso)
    issues = []
    for key in ("id", "title", "publisher", "source_url", "event_at", "observed_at", "unit", "period"):
        if not record.get(key):
            issues.append("MISSING_" + key.upper())
    u = urlparse(str(record.get("source_url", "")))
    if u.scheme != "https" or not u.hostname:
        issues.append("INVALID_SOURCE_URL")
    try:
        event_at = parse_time(record["event_at"])
        received = parse_time(record["observed_at"])
        age = (now - received).total_seconds() / 60
        if age > max_age_minutes:
            issues.append("STALE")
        if age < -2:
            issues.append("FUTURE_OBSERVATION")
    except (ValueError, KeyError, TypeError):
        event_at, age = None, None
        issues.append("INVALID_TIME")
    try:
        actual = parse_number(record.get("actual"))
        forecast = parse_number(record.get("forecast"))
        previous = parse_number(record.get("previous"))
    except (ValueError, TypeError):
        actual = forecast = previous = None
        issues.append("INVALID_NUMBER")
    if record.get("verified_primary") is not True:
        issues.append("PRIMARY_SOURCE_UNVERIFIED")
    if actual is None:
        issues.append("NO_ACTUAL")
    if forecast is None:
        issues.append("NO_FORECAST")
    try:
        if not record.get("forecast_asof") or (event_at and parse_time(record["forecast_asof"]) > event_at):
            issues.append("FORECAST_SNAPSHOT_INVALID")
    except (ValueError, TypeError):
        issues.append("FORECAST_SNAPSHOT_INVALID")
    good = not issues
    return {
        "id": record.get("id"), "status": "VERIFIED_CURRENT" if good else "UNCERTAIN",
        "reasons": sorted(set(issues)),
        "evidence": {"publisher": record.get("publisher"), "url": record.get("source_url"),
                     "age_minutes": age, "event_at": record.get("event_at")},
        "data": {"actual": actual, "forecast": forecast, "previous": previous,
                 "surprise": actual - forecast if actual is not None and forecast is not None else None,
                 "unit": record.get("unit"), "period": record.get("period")},
        "foresight": {
            "status": "CONDITIONAL" if good else "BLOCKED_UNKNOWN",
            "scenarios": [
                {"name": "base", "condition": "existing trend persists", "probability": None},
                {"name": "upside", "condition": "supportive independent evidence", "probability": None},
                {"name": "downside", "condition": "adverse independent evidence", "probability": None}],
            "note": "No probabilities without out-of-sample calibration; no trading signals."
        }
    }

def deduplicate(records):
    seen, output = set(), []
    for r in records:
        key = (r.get("publisher"), r.get("id"), r.get("period"), r.get("revision", 0))
        if key not in seen:
            seen.add(key)
            output.append(r)
    return output
