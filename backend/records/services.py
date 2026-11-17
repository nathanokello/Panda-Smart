"""Lot, event, loss and verification services.

Other apps (notably planting) call these functions; they never import record
models into their views.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from core import services as core_services
from core.errors import ConflictError
from core.models import Crop, Farmer, User
from records.hashing import canonical_time, compute_hash
from records.models import Lot, LotEvent, VerificationToken


def _number(payload, key, errors, minimum=None, maximum=None, required=True):
    if key not in payload:
        if required:
            errors[key] = ["This field is required."]
        return None
    try:
        value = float(payload[key])
    except (TypeError, ValueError):
        errors[key] = ["Must be a number."]
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
        if pest is not None:
            clean["pest_signs"] = pest
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
        if target and lot and not LotEvent.objects.filter(pk=target, lot=lot).exists():
            errors["corrects_event_id"] = ["No such event on this lot."]
        if reason is not None:
            clean["reason"] = reason

    if errors:
        raise ValidationError(errors)
    return clean


def add_event(actor, lot, event_type, payload):
    """Append one validated, hashed event to a lot's history."""
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
    return event


def lots_for_user(user: User):
    qs = Lot.objects.select_related("farmer", "agent", "crop", "ward")
    if user.role == User.Roles.ADMIN or user.is_superuser:
        return qs
    return qs.filter(farmer__tenant_id=user.tenant_id)


def get_lot_for_user(lot_id, user: User):
    try:
        return lots_for_user(user).get(pk=lot_id)
    except Lot.DoesNotExist as exc:
        raise NotFound("Lot not found.") from exc


def register_lot(actor: User, data: dict):
    """Register a lot, its REGISTERED event, optional moisture event and verify token."""
    farmer = data["farmer"]
    crop = data["crop"]
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


def get_summary(lot: Lot) -> dict:
    """Single definition of loss: latest weight vs initial weight."""
    initial = float(lot.initial_weight_kg)
    weight_event = lot.events.filter(type=LotEvent.Types.WEIGHT_READING).order_by("-sequence").first()
    latest = float(weight_event.payload["weight_kg"]) if weight_event else initial
    moisture_event = (
        lot.events.filter(type=LotEvent.Types.MOISTURE_READING).order_by("-sequence").first()
    )
    loss = initial - latest
    loss_pct = (loss / initial * 100) if initial else 0.0
    return {
        "latest_weight_kg": round(latest, 2),
        "loss_kg": round(loss, 2),
        "loss_pct": round(loss_pct, 2),
        "latest_moisture_pct": (
            round(float(moisture_event.payload["moisture_pct"]), 2) if moisture_event else None
        ),
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


def get_lot_farmer_ids_by_ward(ward_id, crop) -> set:
    """Farmer ids with a lot in this ward/crop, used for dashboard privacy suppression."""
    crop_code = crop.code if isinstance(crop, Crop) else str(crop)
    return set(
        Lot.objects.filter(ward_id=ward_id, crop__code=crop_code).values_list(
            "farmer_id", flat=True
        )
    )


def verification_url(token: VerificationToken) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/verify/{token.token}"


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


def respond_to_verification(token_value: str, action: str, reason: str = None):
    token = _active_token(token_value)
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
