"""Append-only hash chain for lot events (architecture.md Section 5)."""
import hashlib
import json
from datetime import timezone as dt_timezone


def canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_time(value) -> str:
    if isinstance(value, str):
        return value
    return (
        value.astimezone(dt_timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def compute_hash(prev_hash: str, event_type: str, payload: dict, recorded_at) -> str:
    raw = prev_hash + event_type + canonical_json(payload) + canonical_time(recorded_at)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
