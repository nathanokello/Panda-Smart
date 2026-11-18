"""Season history and soil records: helping a farmer learn from past seasons.

Everything here is arithmetic on the farmer's own records plus a few general
soil rules. Nothing is predicted. Soil guidance always ends with "confirm with
an extension officer", because one test and three rules are not a diagnosis.
"""
from decimal import Decimal

from planting.models import SeasonRecord, SoilTest
from records import services as records_services

# General guidance thresholds for maize-based systems in Kenya. Starting
# points for a conversation with an extension officer, not prescriptions.
SOIL_RULES = [
    ("ph", lambda v: v < Decimal("5.5"),
     "Soil is acidic (pH below 5.5). Liming may help; ask an extension officer how much."),
    ("ph", lambda v: v > Decimal("7.5"),
     "Soil is alkaline (pH above 7.5). Some nutrients may be harder for maize to take up."),
    ("organic_carbon_pct", lambda v: v < Decimal("1.0"),
     "Organic matter is low (organic carbon below 1%). Manure, compost or crop residues can help."),
]


def yield_per_acre(record: SeasonRecord):
    if record.harvest_kg is None or not record.acres:
        return None
    return round(float(record.harvest_kg) / float(record.acres), 1)


def soil_guidance(test: SoilTest) -> list:
    notes = []
    for field, check, message in SOIL_RULES:
        value = getattr(test, field)
        if value is not None and check(Decimal(value)):
            notes.append(message)
    if not notes and test.ph is not None:
        notes.append("No warning signs in the values entered.")
    if notes:
        notes.append("This is general guidance. Confirm with an extension officer before buying inputs.")
    return notes


def farmer_history(farmer) -> dict:
    """Per-crop summary of past seasons, with storage loss from Hifadhi Mavuno."""
    records = list(SeasonRecord.objects.filter(farmer=farmer).select_related("crop"))
    losses = records_services.get_loss_by_crop_for_farmer(farmer.id)
    crops = {}
    for record in records:
        entry = crops.setdefault(record.crop.code, {
            "crop": record.crop.code, "seasons": 0, "seasons_with_harvest": 0,
            "yields": [], "best": None,
        })
        entry["seasons"] += 1
        per_acre = yield_per_acre(record)
        if per_acre is not None:
            entry["seasons_with_harvest"] += 1
            entry["yields"].append(per_acre)
            if entry["best"] is None or per_acre > entry["best"]["yield_kg_per_acre"]:
                entry["best"] = {
                    "season": record.season,
                    "variety": record.variety,
                    "methods": record.methods,
                    "yield_kg_per_acre": per_acre,
                }
    summary = []
    for code, entry in crops.items():
        yields = entry.pop("yields")
        loss = losses.get(code)
        summary.append({
            **entry,
            "avg_yield_kg_per_acre": round(sum(yields) / len(yields), 1) if yields else None,
            "storage_lots": loss["lot_count"] if loss else 0,
            "avg_storage_loss_pct": loss["avg_loss_pct"] if loss else None,
        })
    # Crops with storage records but no season records still show their loss.
    for code, loss in losses.items():
        if code not in crops:
            summary.append({"crop": code, "seasons": 0, "seasons_with_harvest": 0, "best": None,
                            "avg_yield_kg_per_acre": None, "storage_lots": loss["lot_count"],
                            "avg_storage_loss_pct": loss["avg_loss_pct"]})
    summary.sort(key=lambda item: (-item["seasons"], item["crop"]))

    latest_soil = SoilTest.objects.filter(farmer=farmer).first()
    return {
        "farmer_id": str(farmer.id),
        "season_count": len(records),
        "crops": summary,
        "latest_soil_test": (
            {"id": str(latest_soil.id), "tested_on": latest_soil.tested_on.isoformat(),
             "guidance": soil_guidance(latest_soil)}
            if latest_soil else None
        ),
    }
