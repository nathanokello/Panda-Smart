"""Planting advice, slot allocation and dashboard services.

Cross-app data comes from service functions only, never from another app's models.
"""
from datetime import timedelta, timezone as dt_timezone
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from core import services as core_services
from core.models import Crop, User, Ward
from planting.models import (
    AdviceRuleSet,
    DemandEstimate,
    MarketPrice,
    PlantingIntent,
    RainfallObservation,
    Slot,
)
from planting.rules.engine import compute_advice, load_file_config
from records import services as records_services

DEFAULT_SEASON = "2026-short-rains"


def _iso(value) -> str:
    return (
        value.astimezone(dt_timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _active_rules() -> dict:
    ruleset = AdviceRuleSet.objects.filter(active=True).order_by("-created_at").first()
    return ruleset.config if ruleset and ruleset.config else load_file_config()


def get_advice(ward: Ward, crop: Crop) -> dict:
    config = _active_rules()
    cutoff = timezone.localdate() - timedelta(days=int(config.get("lookback_days", 30)))
    observations = RainfallObservation.objects.filter(ward=ward, date__gte=cutoff).order_by("date")
    result = compute_advice(config, ward, crop.code, observations)
    return {
        "ward": {"id": str(ward.id), "name": ward.name},
        "crop": crop.code,
        **result,
    }


def _booked_acres(slot: Slot) -> Decimal:
    return sum(
        (intent.acres for intent in PlantingIntent.objects.filter(slot=slot)), Decimal("0")
    )


def get_slots(ward: Ward, crop: Crop, season: str = DEFAULT_SEASON) -> list:
    slots = Slot.objects.filter(ward=ward, crop=crop, season=season).order_by("window_start")
    result = []
    for slot in slots:
        booked = _booked_acres(slot)
        remaining = Decimal(slot.capacity_acres) - booked
        result.append(
            {
                "id": str(slot.id),
                "window_start": slot.window_start.isoformat(),
                "window_end": slot.window_end.isoformat(),
                "capacity_acres": float(slot.capacity_acres),
                "booked_acres": float(booked),
                "remaining_acres": round(float(remaining), 2),
            }
        )
    return result


def register_intent(actor: User, data: dict) -> PlantingIntent:
    farmer = data["farmer"]
    crop = data["crop"]
    acres = Decimal(str(data["acres"]))
    season = data.get("season") or DEFAULT_SEASON

    if not core_services.farmer_is_visible(farmer, actor):
        raise ValidationError({"farmer_id": ["You may only register intents for your tenant."]})

    slots = list(
        Slot.objects.filter(ward=farmer.ward, crop=crop, season=season).order_by("window_start")
    )
    demand = DemandEstimate.objects.filter(
        ward=farmer.ward, crop=crop, season=season
    ).first()
    expected = (
        Decimal(demand.expected_demand_acres)
        if demand
        else sum((Decimal(slot.capacity_acres) for slot in slots), Decimal("0"))
    )
    planned = sum(
        (
            intent.acres
            for intent in PlantingIntent.objects.filter(
                farmer__ward=farmer.ward, crop=crop, season=season
            )
        ),
        Decimal("0"),
    ) + acres

    oversubscribed = expected > 0 and planned > expected
    chosen = None
    if slots:
        if oversubscribed:
            # Move the farmer to a later window when demand is exceeded.
            chosen = slots[-1]
        else:
            for slot in slots:
                if _booked_acres(slot) + acres <= Decimal(slot.capacity_acres):
                    chosen = slot
                    break
            if chosen is None:
                chosen = max(slots, key=lambda slot: Decimal(slot.capacity_acres) - _booked_acres(slot))

    alternatives = []
    warning = ""
    if oversubscribed:
        warning = (
            f"{crop.name_en} in this ward is above expected demand. "
            "You have been moved to a later window."
        )
        for other in Crop.objects.exclude(pk=crop.pk):
            other_demand = DemandEstimate.objects.filter(
                ward=farmer.ward, crop=other, season=season
            ).first()
            other_expected = (
                Decimal(other_demand.expected_demand_acres) if other_demand else Decimal("0")
            )
            other_planned = sum(
                (
                    intent.acres
                    for intent in PlantingIntent.objects.filter(
                        farmer__ward=farmer.ward, crop=other, season=season
                    )
                ),
                Decimal("0"),
            )
            if other_expected == 0 or other_planned < other_expected:
                alternatives.append(
                    {"crop": other.code, "reason": "Lower planned acreage in your ward"}
                )
            if len(alternatives) == 2:
                break

    return PlantingIntent.objects.create(
        farmer=farmer,
        plot=data.get("plot"),
        crop=crop,
        acres=acres,
        season=season,
        slot=chosen,
        oversubscribed=oversubscribed,
        warning=warning,
        alternatives=alternatives,
    )


def intents_for_user(user: User):
    qs = PlantingIntent.objects.select_related("farmer", "crop", "plot", "slot")
    if user.role == User.Roles.ADMIN or user.is_superuser:
        return qs
    if user.role == User.Roles.FARMER:
        return qs.filter(farmer__user=user)
    return qs.filter(farmer__tenant_id=user.tenant_id)


def _sell_flag(latest_price, average_price):
    if latest_price is None or average_price is None:
        return "watch", "No recent price data; monitor the market before selling."
    difference = (latest_price - average_price) / average_price * 100
    if difference <= -10:
        return "hold", f"Price is {abs(difference):.0f}% below the 3-month average."
    if difference >= 10:
        return "sell_now", f"Price is {difference:.0f}% above the 3-month average."
    return "watch", "Price is close to the 3-month average."


def get_dashboard_wards() -> list:
    generated_at = _iso(timezone.now())
    rows = []
    for ward in Ward.objects.all():
        intents = PlantingIntent.objects.filter(farmer__ward=ward)
        stock = sum(
            records_services.get_stock_by_ward(ward.id, crop)["stored_kg"]
            for crop in Crop.objects.filter(storable=True)
        )
        rows.append(
            {
                "id": str(ward.id),
                "name": ward.name,
                "county": ward.county,
                "region": ward.region,
                "crop_count": Crop.objects.filter(
                    Q(intents__farmer__ward=ward)
                    | Q(lots__ward=ward)
                    | Q(demand__ward=ward)
                )
                .distinct()
                .count(),
                "total_intended_acres": round(
                    float(sum((intent.acres for intent in intents), Decimal("0"))), 2
                ),
                "stored_stock_kg": round(stock, 2),
                "generated_at": generated_at,
            }
        )
    return rows


def get_ward_dashboard(ward_id) -> dict:
    ward = core_services.get_ward_or_404(ward_id)
    crops = []
    for crop in Crop.objects.all():
        intents = PlantingIntent.objects.filter(farmer__ward=ward, crop=crop)
        intended = sum((intent.acres for intent in intents), Decimal("0"))
        demand = DemandEstimate.objects.filter(
            ward=ward, crop=crop, season=DEFAULT_SEASON
        ).first()
        expected = Decimal(demand.expected_demand_acres) if demand else Decimal("0")
        stock = records_services.get_stock_by_ward(ward.id, crop)
        latest = (
            MarketPrice.objects.filter(ward=ward, crop=crop).order_by("-date").first()
        )
        average = None
        if latest:
            recent = MarketPrice.objects.filter(
                ward=ward,
                crop=crop,
                date__gte=latest.date - timedelta(days=90),
                date__lte=latest.date,
            )
            prices = [Decimal(item.price_per_kg_kes) for item in recent]
            if prices:
                average = sum(prices) / len(prices)

        farmer_ids = set(intents.values_list("farmer_id", flat=True))
        farmer_ids |= records_services.get_lot_farmer_ids_by_ward(ward.id, crop)
        suppressed = len(farmer_ids) < 5

        if suppressed:
            sell_flag = None
            sell_flag_reason = "Suppressed: fewer than 5 farmers for this crop in this ward."
        else:
            sell_flag, sell_flag_reason = _sell_flag(
                Decimal(latest.price_per_kg_kes) if latest else None, average
            )

        crops.append(
            {
                "crop": crop.code,
                "intended_acres": None if suppressed else round(float(intended), 2),
                "expected_demand_acres": None if suppressed else round(float(expected), 2),
                "oversubscription_pct": (
                    None
                    if suppressed
                    else round(float(intended / expected * 100), 2) if expected else 0.0
                ),
                "stored_stock_kg": None if suppressed else stock["stored_kg"],
                "avg_loss_pct": None if suppressed else stock["avg_loss_pct"],
                "latest_price_per_kg_kes": (
                    None if suppressed or not latest else float(latest.price_per_kg_kes)
                ),
                "sell_flag": sell_flag,
                "sell_flag_reason": sell_flag_reason,
                "suppressed": suppressed,
            }
        )

    return {
        "ward": {"id": str(ward.id), "name": ward.name, "county": ward.county},
        "generated_at": _iso(timezone.now()),
        "crops": crops,
    }
