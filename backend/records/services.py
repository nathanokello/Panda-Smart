"""Lot, event, loss and verification services.

Other apps (notably planting) call these functions; they never import record
models into their views.
"""
import math
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from core import services as core_services
from core.errors import ConflictError
from core.models import Crop, Farmer, User
from records.hashing import canonical_time, compute_hash
from records.models import Lot, LotEvent, ScheduledCheck, VerificationToken


# Event types a storage agent may add by hand. The rest are system-written.
STAFF_EVENT_TYPES = (
    LotEvent.Types.MOISTURE_READING,
    LotEvent.Types.WEIGHT_READING,
    LotEvent.Types.CHECKUP,
    LotEvent.Types.LOSS_RECORDED,
    LotEvent.Types.CORRECTION,
)


def _number(payload, key, errors, minimum=None, maximum=None, required=True):
    if key not in payload:
        if required:
            errors[key] = ["This field is required."]
        return None
    if isinstance(payload[key], bool):
        errors[key] = ["Must be a number."]
        return None
    try:
        value = float(payload[key])
    except (TypeError, ValueError):
        errors[key] = ["Must be a number."]
        return None
    if not math.isfinite(value):  # "nan" and "inf" parse as floats but are not readings
        errors[key] = ["Must be a finite number."]
        return None
    if minimum is not None and value < minimum:
        errors[key] = [f"Must be at least {minimum}."]
    if maximum is not None and value > maximum:
        errors[key] = [f"Must be at most {maximum}."]
    return value


def _integer(payload, key, errors, minimum=None, required=True):
    value = _number(payload, key, errors, minimum=minimum, required=required)
    return int(value) if value is not None else None


def _text(payload, key, errors, required=True, allow_blank=False):
    if key not in payload:
        if required:
            errors[key] = ["This field is required."]
        return None
    value = payload[key]
    if not isinstance(value, str):
        errors[key] = ["Must be a string."]
        return None
    if not allow_blank and not value.strip():
        errors[key] = ["This field may not be blank."]
        return None
    return value.strip()


def _boolean(payload, key, errors):
    if key not in payload or not isinstance(payload[key], bool):
        errors[key] = ["Must be a boolean."]
        return None
    return payload[key]


def validate_event_payload(event_type, payload, lot=None):
    """Validate and normalise an event payload against the agreed event table."""
    if event_type not in LotEvent.Types.values:
        raise ValidationError({"type": ["Unknown event type."]})
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValidationError({"payload": ["Must be a JSON object."]})

    errors = {}
    clean = dict(payload)
    if event_type == "REGISTERED":
        weight = _number(payload, "weight_kg", errors, minimum=0)
        bags = _integer(payload, "bag_count", errors, minimum=0)
        method = _text(payload, "storage_method", errors)
        if weight is not None:
            clean["weight_kg"] = weight
        if bags is not None:
            clean["bag_count"] = bags
        if method is not None:
            clean["storage_method"] = method
    elif event_type == "MOISTURE_READING":
        moisture = _number(payload, "moisture_pct", errors, minimum=0, maximum=100)
        if moisture is not None:
            clean["moisture_pct"] = moisture
    elif event_type == "WEIGHT_READING":
        weight = _number(payload, "weight_kg", errors, minimum=0)
        if weight is not None:
            clean["weight_kg"] = weight
    elif event_type == "CHECKUP":
        pest = _boolean(payload, "pest_signs", errors)
        notes = _text(payload, "notes", errors, required=False, allow_blank=True)
        moisture = _number(payload, "moisture_pct", errors, minimum=0, maximum=100, required=False)
        good_weight = _number(payload, "good_weight_kg", errors, minimum=0, required=False)
        if pest is not None:
            clean["pest_signs"] = pest
        if moisture is not None:
            clean["moisture_pct"] = moisture
        if good_weight is not None:
            clean["good_weight_kg"] = good_weight
        clean["notes"] = notes or ""
    elif event_type == "LOSS_RECORDED":
        loss = _number(payload, "loss_kg", errors, minimum=0)
        cause = _text(payload, "cause", errors)
        if loss is not None:
            clean["loss_kg"] = loss
        if cause is not None:
            clean["cause"] = cause
    elif event_type == "VERIFIED":
        method = _text(payload, "method", errors)
        if method is not None and method not in ("link", "sms"):
            errors["method"] = ["Must be 'link' or 'sms'."]
    elif event_type == "DISPUTED":
        reason = _text(payload, "reason", errors)
        if reason is not None:
            clean["reason"] = reason
    elif event_type == "CORRECTION":
        target = _text(payload, "corrects_event_id", errors)
        new_payload = payload.get("new_payload")
        reason = _text(payload, "reason", errors)
        if not isinstance(new_payload, dict):
            errors["new_payload"] = ["Must be a JSON object."]
        else:
            # Corrected figures feed the loss calculation, so check them like
            # the original readings.
            sub_errors = {}
            if "weight_kg" in new_payload:
                value = _number(new_payload, "weight_kg", sub_errors, minimum=0)
                if value is not None:
                    new_payload = {**new_payload, "weight_kg": value}
            if "moisture_pct" in new_payload:
                value = _number(new_payload, "moisture_pct", sub_errors, minimum=0, maximum=100)
                if value is not None:
                    new_payload = {**new_payload, "moisture_pct": value}
            if sub_errors:
                errors["new_payload"] = [
                    f"{key}: {messages[0]}" for key, messages in sub_errors.items()
                ]
            else:
                clean["new_payload"] = new_payload
        if target:
            try:
                uuid.UUID(target)
            except ValueError:
                errors["corrects_event_id"] = ["Must be a valid event id."]
            else:
                if lot and not LotEvent.objects.filter(pk=target, lot=lot).exists():
                    errors["corrects_event_id"] = ["No such event on this lot."]
        if reason is not None:
            clean["reason"] = reason

    if errors:
        raise ValidationError(errors)
    return clean


def _moisture_limit(lot: Lot):
    if lot.crop.code == "maize":
        return float(getattr(settings, "HIFADHI_MAIZE_MAX_MOISTURE_PCT", 13.0))
    return None


def _schedule(lot: Lot, kind: str, due_at):
    return ScheduledCheck.objects.create(lot=lot, kind=kind, due_at=due_at)


def complete_scheduled_check(lot: Lot, payload):
    check = lot.scheduled_checks.filter(
        kind=ScheduledCheck.Types.CHECKUP, completed_at__isnull=True
    ).order_by("due_at").first()
    if check:
        check.completed_at = timezone.now()
        check.moisture_pct = payload.get("moisture_pct")
        check.good_weight_kg = payload.get("good_weight_kg")
        check.pests = payload.get("pest_signs")
        check.save(update_fields=["completed_at", "moisture_pct", "good_weight_kg", "pests"])


def process_moisture_reading(lot: Lot, moisture_pct):
    """Apply the v10 follow-up rule: dry, re-test, or extension-officer referral."""
    limit = _moisture_limit(lot)
    if limit is None:
        lot.moisture_status = Lot.MoistureStatuses.UNKNOWN
        lot.next_check_at = None
        lot.save(update_fields=["moisture_status", "next_check_at"])
        return

    is_dry = float(moisture_pct) <= limit
    if is_dry:
        lot.moisture_status = Lot.MoistureStatuses.DRY
        lot.next_check_at = timezone.now() + timedelta(days=14)
        lot.save(update_fields=["moisture_status", "next_check_at"])
        lot.scheduled_checks.filter(kind=ScheduledCheck.Types.RETEST, completed_at__isnull=True).update(
            completed_at=timezone.now()
        )
        now = timezone.now()
        if not lot.scheduled_checks.filter(kind=ScheduledCheck.Types.CHECKUP).exists():
            for days in getattr(settings, "HIFADHI_CHECK_DAYS", (14, 30, 60)):
                _schedule(lot, ScheduledCheck.Types.CHECKUP, now + timedelta(days=int(days)))
        recorded_at = timezone.now()
        previous = lot.events.order_by("-sequence").first()
        payload = {"moisture_pct": float(moisture_pct), "limit_pct": limit, "decision": "dry enough"}
        LotEvent.objects.create(
            lot=lot,
            type=LotEvent.Types.SYSTEM_DECISION,
            payload=payload,
            recorded_by=None,
            recorded_at=recorded_at,
            sequence=(previous.sequence + 1),
            prev_hash=previous.hash,
            hash=compute_hash(
                previous.hash,
                LotEvent.Types.SYSTEM_DECISION,
                payload,
                recorded_at,
            ),
        )
        return

    if lot.moisture_status == Lot.MoistureStatuses.RETEST:
        lot.retest_count += 1
    else:
        lot.retest_count = 0
    if lot.retest_count >= 3:
        lot.moisture_status = Lot.MoistureStatuses.OFFICER
        lot.next_check_at = None
    else:
        lot.moisture_status = Lot.MoistureStatuses.RETEST
        lot.next_check_at = timezone.now() + timedelta(days=2)
        lot.scheduled_checks.filter(kind=ScheduledCheck.Types.RETEST, completed_at__isnull=True).delete()
        _schedule(lot, ScheduledCheck.Types.RETEST, lot.next_check_at)
    lot.save(update_fields=["moisture_status", "retest_count", "next_check_at"])


@transaction.atomic
def add_event(actor, lot, event_type, payload):
    """Append one validated, hashed event to a lot's history.

    The lot row is locked first, so two requests at the same moment cannot both
    read the same "previous" event and break the hash chain (or hit the unique
    sequence constraint and return a 500).
    """
    Lot.objects.select_for_update().get(pk=lot.pk)
    clean_payload = validate_event_payload(event_type, payload, lot=lot)
    previous = lot.events.order_by("-sequence").first()
    event = LotEvent(
        lot=lot,
        type=event_type,
        payload=clean_payload,
        recorded_by=actor if actor and actor.is_authenticated else None,
        recorded_at=timezone.now(),
        sequence=previous.sequence + 1 if previous else 1,
        prev_hash=previous.hash if previous else "",
    )
    event.hash = compute_hash(event.prev_hash, event.type, event.payload, event.recorded_at)
    event.save()
    if event_type == LotEvent.Types.DISPUTED and lot.status != Lot.Statuses.DISPUTED:
        lot.status = Lot.Statuses.DISPUTED
        lot.save(update_fields=["status"])
    if event_type == LotEvent.Types.MOISTURE_READING:
        process_moisture_reading(lot, clean_payload["moisture_pct"])
    if event_type == LotEvent.Types.CHECKUP:
        complete_scheduled_check(lot, clean_payload)
    return event


def lots_for_user(user: User):
    qs = Lot.objects.select_related("farmer", "agent", "crop", "ward")
    if user.role == User.Roles.ADMIN or user.is_superuser:
        return qs
    if user.role == User.Roles.FARMER:
        profile = getattr(user, "farmer_profile", None)
        return qs.filter(farmer=profile) if profile else qs.none()
    if user.tenant_id is None:
        # filter(tenant_id=None) would match every farmer with no cooperative.
        return qs.none()
    return qs.filter(farmer__tenant_id=user.tenant_id)


def get_lot_for_user(lot_id, user: User):
    try:
        return lots_for_user(user).get(pk=lot_id)
    except Lot.DoesNotExist as exc:
        raise NotFound("Lot not found.") from exc


@transaction.atomic
def register_lot(actor: User, data: dict):
    """Register a lot, its REGISTERED event, optional moisture event and verify token."""
    farmer = data["farmer"]
    crop = data["crop"]
    if not crop.storable:
        raise ValidationError({"crop": [f"{crop.name_en} cannot be registered as a stored lot."]})
    if not farmer.consent_given:
        raise ValidationError({"farmer_id": ["Farmer consent is required."]})
    if not core_services.farmer_is_visible(farmer, actor):
        raise ValidationError({"farmer_id": ["You may only register lots for your tenant."]})

    lot = Lot.objects.create(
        farmer=farmer,
        agent=actor,
        crop=crop,
        ward=farmer.ward,
        initial_weight_kg=data["weight_kg"],
        location_label=data["location_label"],
        status=Lot.Statuses.STORED,
    )
    add_event(
        actor,
        lot,
        LotEvent.Types.REGISTERED,
        {
            "weight_kg": float(data["weight_kg"]),
            "bag_count": int(data["bag_count"]),
            "storage_method": data["storage_method"],
        },
    )
    if data.get("moisture_pct") is not None:
        add_event(
            actor,
            lot,
            LotEvent.Types.MOISTURE_READING,
            {"moisture_pct": float(data["moisture_pct"])},
        )
    token = VerificationToken.objects.create(lot=lot, farmer=farmer)
    return lot, token


def _corrected_payloads(lot: Lot) -> dict:
    """Map event id -> payload after applying the latest CORRECTION for it.

    Events are never edited. A correction is a new event; this applies it
    when reading, so the original stays in the history.
    """
    corrected = {}
    for event in lot.events.filter(type=LotEvent.Types.CORRECTION).order_by("sequence"):
        target = str(event.payload.get("corrects_event_id", ""))
        if target and isinstance(event.payload.get("new_payload"), dict):
            corrected[target] = event.payload["new_payload"]
    return corrected


def _value(event, key, corrected):
    payload = {**event.payload, **corrected.get(str(event.id), {})}
    return float(payload[key]) if payload.get(key) is not None else None


def get_summary(lot: Lot) -> dict:
    """Single definition of loss: latest weight vs initial weight.

    loss_kg = initial_weight_kg - latest_weight_kg
    Corrections to the REGISTERED, WEIGHT_READING and MOISTURE_READING events
    are applied. This is a raw weight difference: it does not adjust for
    moisture, so drying counts as loss (see README, open decisions).
    """
    corrected = _corrected_payloads(lot)
    initial = float(lot.initial_weight_kg)
    registered = lot.events.filter(type=LotEvent.Types.REGISTERED).order_by("sequence").first()
    if registered:
        initial = _value(registered, "weight_kg", corrected) or initial
    weight_event = lot.events.filter(type=LotEvent.Types.WEIGHT_READING).order_by("-sequence").first()
    latest = _value(weight_event, "weight_kg", corrected) if weight_event else initial
    if latest is None:
        latest = initial
    moisture_event = (
        lot.events.filter(type=LotEvent.Types.MOISTURE_READING).order_by("-sequence").first()
    )
    moisture = _value(moisture_event, "moisture_pct", corrected) if moisture_event else None
    loss = initial - latest
    loss_pct = (loss / initial * 100) if initial else 0.0

    initial_moisture_event = lot.events.filter(
        type=LotEvent.Types.MOISTURE_READING
    ).order_by("sequence").first()
    initial_moisture = (
        _value(initial_moisture_event, "moisture_pct", corrected)
        if initial_moisture_event else None
    )
    dry_matter_latest = latest
    dry_matter_loss = loss
    if initial_moisture is not None and moisture is not None:
        initial_fraction = max(0.0, 1.0 - initial_moisture / 100.0)
        latest_fraction = max(0.01, 1.0 - moisture / 100.0)
        dry_matter_latest = initial * initial_fraction / latest_fraction
        dry_matter_loss = max(0.0, initial - dry_matter_latest)
    dry_matter_loss_pct = (dry_matter_loss / initial * 100) if initial else 0.0
    return {
        "initial_weight_kg": round(initial, 2),
        "latest_weight_kg": round(latest, 2),
        "loss_kg": round(loss, 2),
        "loss_pct": round(loss_pct, 2),
        "latest_moisture_pct": round(moisture, 2) if moisture is not None else None,
        "dry_matter_latest_weight_kg": round(dry_matter_latest, 2),
        "dry_matter_loss_kg": round(dry_matter_loss, 2),
        "dry_matter_loss_pct": round(dry_matter_loss_pct, 2),
    }


def verify_chain(lot: Lot) -> bool:
    previous_hash = ""
    for event in lot.events.order_by("sequence"):
        expected = compute_hash(previous_hash, event.type, event.payload, event.recorded_at)
        if event.prev_hash != previous_hash or event.hash != expected:
            return False
        previous_hash = event.hash
    return True


def get_stock_by_ward(ward_id, crop) -> dict:
    """Integration point promised to the planting app (architecture.md Section 9)."""
    crop_code = crop.code if isinstance(crop, Crop) else str(crop)
    lots = Lot.objects.filter(ward_id=ward_id, crop__code=crop_code, status=Lot.Statuses.STORED)
    lot_count = lots.count()
    if not lot_count:
        return {"stored_kg": 0.0, "avg_loss_pct": 0.0, "lot_count": 0}
    summaries = [get_summary(lot) for lot in lots]
    return {
        "stored_kg": round(sum(item["latest_weight_kg"] for item in summaries), 2),
        "avg_loss_pct": round(
            sum(item["loss_pct"] for item in summaries) / lot_count, 2
        ),
        "lot_count": lot_count,
    }


def get_lots_for_farmer(farmer_id):
    """A farmer's own lots, newest first. Used by the farmer dashboard summary."""
    return Lot.objects.filter(farmer_id=farmer_id).select_related("crop", "ward").order_by(
        "-registered_at"
    )


def get_lot_farmer_ids_by_ward(ward_id, crop) -> set:
    """Farmer ids with a lot in this ward/crop, used for dashboard privacy suppression."""
    crop_code = crop.code if isinstance(crop, Crop) else str(crop)
    return set(
        Lot.objects.filter(ward_id=ward_id, crop__code=crop_code).values_list(
            "farmer_id", flat=True
        )
    )


def verification_url(token: VerificationToken) -> str:
    """Farmer-facing link. The HTML frontend uses verify.html?token=<token>.

    FRONTEND_VERIFY_PATH can be set to "/verify/" for a frontend with
    path-based routing (the React app in the architecture).
    """
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    path = getattr(settings, "FRONTEND_VERIFY_PATH", "/verify.html?token=")
    return f"{base}{path}{token.token}"


def _active_token(token_value: str) -> VerificationToken:
    token = (
        VerificationToken.objects.select_related("lot__farmer", "lot__crop", "farmer__user")
        .filter(token=token_value)
        .first()
    )
    if not token:
        raise NotFound("Verification link not found.")
    if token.expires_at < timezone.now():
        raise ConflictError("This verification link has expired.")
    return token


def get_verification_data(token_value: str) -> dict:
    token = _active_token(token_value)
    lot = token.lot
    events = [
        {
            "id": str(event.id),
            "type": event.type,
            "recorded_at": canonical_time(event.recorded_at),
            "payload": event.payload,
        }
        for event in lot.events.order_by("sequence")
    ]
    return {
        "lot": {
            "id": str(lot.id),
            "crop": lot.crop.code,
            "initial_weight_kg": float(lot.initial_weight_kg),
            "status": lot.status,
        },
        "farmer_name": token.farmer.name,
        "events": events,
        "summary": get_summary(lot),
        "already_responded": bool(token.used_at),
    }


@transaction.atomic
def respond_to_verification(token_value: str, action: str, reason: str = None):
    _active_token(token_value)  # 404 / expired checks
    # Re-read under a row lock so a double tap cannot record two responses.
    # No select_related here: PostgreSQL cannot lock the nullable side of a join.
    token = VerificationToken.objects.select_for_update().get(token=token_value)
    if token.used_at:
        raise ConflictError("This verification link has already been used.")

    if action == "confirm":
        event_type = LotEvent.Types.VERIFIED
        payload = {"method": "link"}
    elif action == "dispute":
        event_type = LotEvent.Types.DISPUTED
        payload = {"reason": reason}
    else:
        raise ValidationError({"action": ["Must be 'confirm' or 'dispute'."]})

    actor = token.farmer.user
    event = add_event(actor, token.lot, event_type, payload)
    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])
    return event


def get_verification_links_for_phone(phone: str):
    """Used by the USSD 'verify my grain' menu."""
    tokens = (
        VerificationToken.objects.filter(
            farmer__phone=phone, used_at__isnull=True, expires_at__gte=timezone.now()
        )
        .select_related("lot")
        .order_by("-created_at")[:3]
    )
    return [verification_url(token) for token in tokens]


def get_verification_links_for_farmer(farmer_id):
    """Pending links for one farmer, looked up by farmer id.

    Looking up by the login's phone number fails whenever the login phone and the
    farmer record phone differ (as in the demo seed data).
    """
    tokens = VerificationToken.objects.filter(
        farmer_id=farmer_id, used_at__isnull=True, expires_at__gte=timezone.now()
    ).order_by("-created_at")[:10]
    return [verification_url(token) for token in tokens]


def get_loss_by_crop_for_farmer(farmer_id) -> dict:
    """Storage loss per crop for one farmer: {crop_code: {lot_count, avg_loss_pct}}.

    Used by the season history so a farmer sees storage loss next to yield.
    """
    result = {}
    for lot in Lot.objects.filter(farmer_id=farmer_id).select_related("crop"):
        entry = result.setdefault(lot.crop.code, {"lot_count": 0, "loss_pcts": []})
        entry["lot_count"] += 1
        entry["loss_pcts"].append(get_summary(lot)["loss_pct"])
    return {
        code: {
            "lot_count": item["lot_count"],
            "avg_loss_pct": round(sum(item["loss_pcts"]) / item["lot_count"], 2),
        }
        for code, item in result.items()
    }
