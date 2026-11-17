"""Plain-Python rules engine for planting advice. No ML, no external services."""
import json
from datetime import date, timedelta
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("v1.json")


def load_file_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def compute_advice(config: dict, ward, crop_code: str, observations) -> dict:
    """Turn rainfall observations into a planting window and confidence.

    `observations` is any iterable of objects exposing `date` and `rainfall_mm`.
    """
    crop_config = config.get("crop_windows", {}).get(crop_code, {})
    duration = int(crop_config.get("duration_days", config.get("default_duration_days", 10)))
    threshold = float(config.get("rainfall_onset_threshold_mm", 20))
    region = getattr(ward, "region", "other") or "other"
    adjustment = config.get("region_adjustments", {}).get(region, {})
    shift = int(adjustment.get("window_shift_days", 0))
    base_confidence = float(crop_config.get("confidence", config.get("base_confidence", 0.65)))
    base_confidence += float(adjustment.get("confidence_delta", 0))

    cumulative = 0.0
    rainy_days = 0
    onset = None
    for observation in observations:
        rainfall = float(observation.rainfall_mm)
        cumulative += rainfall
        if rainfall > 0:
            rainy_days += 1
        if onset is None and cumulative >= threshold:
            onset = observation.date

    if onset is None:
        start = date.today() + timedelta(days=int(config.get("fallback_offset_days", 12)))
        confidence = base_confidence - 0.15
        rationale = "Rainfall onset has not been observed yet; using the seasonal typical window."
    else:
        start = onset + timedelta(days=shift)
        confidence = base_confidence + min(0.2, rainy_days * 0.02)
        rationale = crop_config.get("rationale") or f"Rainfall onset observed around {onset}."

    end = start + timedelta(days=duration - 1)
    confidence = round(max(0.1, min(0.95, confidence)), 2)
    return {
        "recommended_window": {"start": start.isoformat(), "end": end.isoformat()},
        "confidence": confidence,
        "rationale": rationale,
        "rule_set_version": config.get("version", "v1"),
        "alternatives": list(config.get("alternatives", {}).get(crop_code, [])),
    }
