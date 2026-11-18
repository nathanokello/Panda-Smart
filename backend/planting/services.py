"""Planting advice, slot allocation and dashboard services.

Cross-app data comes from service functions only, never from another app's models.
"""
from datetime import timedelta, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from core import services as core_services
from core.models import Crop, Plot, User, Ward
from planting.models import (
    AdviceRuleSet,
    DemandEstimate,
    MarketPrice,
    PlantingIntent,
    RainfallObservation,
    Slot,
)
from planting.rules.engine import compute_advice, load_file_config
from planting import weather
from records import services as records_services

DEFAULT_SEASON = "2026-short-rains"


def _iso(value) -> str:
    return (
        value.astimezone(dt_timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


def _active_rules() -> dict:
    ruleset = AdviceRuleSet.objects.filter(active=True).order_by("-created_at").first()
    return ruleset.config if ruleset and ruleset.config else load_file_config()


def _rainfall_from_one_source(ward: Ward, cutoff):
    """Rainfall for the ward from ONE source only.

    The rules add rainfall up, so mixing two sources for the same days (for
    example demo CHIRPS rows and NASA POWER rows) would count the rain twice.
    Sources are tried in RAINFALL_SOURCE_PRIORITY order.
    """
    qs = RainfallObservation.objects.filter(ward=ward, date__gte=cutoff)
    available = set(qs.values_list("source", flat=True))
    priority = list(getattr(settings, "RAINFALL_SOURCE_PRIORITY", ["NASA_POWER", "CHIRPS"]))
    chosen = next((source for source in priority if source in available), None)
    if chosen is None and available:
        chosen = sorted(available)[0]
    return qs.filter(source=chosen).order_by("date") if chosen else qs.none()


def get_advice(ward: Ward, crop: Crop) -> dict:
    config = _active_rules()
    cutoff = timezone.localdate() - timedelta(days=int(config.get("lookback_days", 30)))
    observations = _rainfall_from_one_source(ward, cutoff)
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
    plot = data.get("plot")
    if plot is not None and plot.farmer_id != farmer.id:
        raise ValidationError({"plot_id": ["This plot does not belong to the farmer."]})

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
    if user.tenant_id is None:
        return qs.none()
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
        # Same season as the demand estimate below; otherwise last season's plans
        # inflate "above demand".
        intents = PlantingIntent.objects.filter(
            farmer__ward=ward, crop=crop, season=DEFAULT_SEASON
        )
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
                # Share of planned acres above expected demand: 120 planned
                # against 90 expected is 33.33 (architecture.md 6.4). 0 when
                # planting is at or below demand.
                "oversubscription_pct": (
                    None
                    if suppressed
                    else round(max(0.0, float((intended - expected) / expected * 100)), 2)
                    if expected
                    else 0.0
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


def get_ward_weather(ward: Ward) -> dict:
    """7-day forecast for a ward, cached for an hour. Shared by WardWeatherView
    and the farmer dashboard so both report the exact same numbers."""
    if not getattr(settings, "OPEN_METEO_ENABLED", False):
        return {"enabled": False}
    if ward.lat is None or ward.lng is None:
        return {"enabled": True, "ward": ward.name, "days": [],
                 "message": "This ward has no coordinates yet."}
    key = f"weather:open-meteo:{ward.id}"
    days = cache.get(key)
    if days is None:
        days = weather.fetch_open_meteo_forecast(float(ward.lat), float(ward.lng))
        cache.set(key, days, 60 * 60)
    return {
        "enabled": True,
        "ward": ward.name,
        "provider": "Open-Meteo",
        "attribution": "Weather data by Open-Meteo.com (CC BY 4.0)",
        "days": days,
    }


def _recommended_crop_code(farmer, active_codes) -> str:
    if active_codes:
        return active_codes[0]
    storable = Crop.objects.filter(storable=True).order_by("code").first()
    return storable.code if storable else "maize"


def get_farmer_dashboard(user: User) -> dict:
    """Everything the farmer dashboard home screen needs, in one call.

    Reuses the same advice engine, lot summaries and weather cache as the
    rest of the API so the numbers always match the detail screens.
    """
    farmer = getattr(user, "farmer_profile", None)
    if farmer is None:
        raise NotFound("This account has no farmer profile.")

    plots = list(Plot.objects.filter(farmer=farmer).select_related("ward").order_by("created_at"))
    total_acres = sum((Decimal(p.acres) for p in plots), Decimal("0"))

    intents = list(
        PlantingIntent.objects.filter(farmer=farmer, season=DEFAULT_SEASON).select_related("crop")
    )
    active_codes = sorted({intent.crop.code for intent in intents})

    lots = list(records_services.get_lots_for_farmer(farmer.id))
    stored_kg = 0.0
    for lot in lots:
        if lot.status in ("stored", "disputed"):
            stored_kg += records_services.get_summary(lot)["latest_weight_kg"]

    recommendation = None
    crop_code = _recommended_crop_code(farmer, active_codes)
    try:
        crop = core_services.get_crop_or_404(crop_code)
        recommendation = get_advice(farmer.ward, crop)
    except NotFound:
        recommendation = None

    weather_data = {"enabled": False}
    try:
        weather_data = get_ward_weather(farmer.ward)
    except weather.WeatherSourceError:
        weather_data = {"enabled": True, "ward": farmer.ward.name, "days": [],
                         "message": "The weather service could not be reached."}

    activity = []
    for intent in sorted(intents, key=lambda i: i.created_at, reverse=True)[:3]:
        activity.append({
            "type": "planting_intent",
            "label": f"Planting intent registered",
            "detail": f"{intent.acres} acres of {intent.crop.name_en}",
            "at": _iso(intent.created_at),
        })
    from records.models import LotEvent
    events = LotEvent.objects.filter(lot__farmer=farmer).select_related("lot__crop").order_by(
        "-recorded_at"
    )[:4]
    for event in events:
        activity.append({
            "type": "lot_event",
            "label": event.get_type_display(),
            "detail": f"{event.lot.crop.name_en} - {event.lot.location_label}",
            "at": _iso(event.recorded_at),
        })
    activity.append({
        "type": "profile",
        "label": "Profile created",
        "detail": farmer.name,
        "at": _iso(farmer.created_at),
    })
    activity.sort(key=lambda row: row["at"], reverse=True)

    primary_plot = plots[0] if plots else None
    latest_intent = intents[0] if intents else None

    return {
        "farmer": {"id": str(farmer.id), "name": farmer.name, "ward": farmer.ward.name},
        "stats": {
            "farms": len(plots),
            "total_acres": round(float(total_acres), 2),
            "active_crops": len(active_codes),
            "active_crop_codes": active_codes,
            "stored_produce_kg": round(stored_kg, 2),
            "stored_produce_tonnes": round(stored_kg / 1000, 2),
        },
        "primary_farm": None if primary_plot is None else {
            "id": str(primary_plot.id),
            "ward": primary_plot.ward.name,
            "acres": float(primary_plot.acres),
            "crop": latest_intent.crop.name_en if latest_intent else None,
        },
        "ai_recommendation": recommendation,
        "weather": weather_data,
        "recent_activity": activity[:5],
        "season": DEFAULT_SEASON,
    }
