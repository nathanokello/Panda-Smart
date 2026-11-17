"""Shared service functions.

Other apps call these instead of importing core models into their views.
"""
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from core.models import Crop, Farmer, User, Ward


def tenant_scope(user: User):
    """Return the tenant id the user may see, or None for unrestricted admins."""
    if not user or not user.is_authenticated:
        return None
    if user.role == User.Roles.ADMIN or user.is_superuser:
        return None
    return user.tenant_id


def farmers_for_user(user: User):
    qs = Farmer.objects.select_related("ward", "tenant")
    tenant_id = tenant_scope(user)
    if tenant_id is not None:
        qs = qs.filter(tenant_id=tenant_id)
    return qs


def farmer_is_visible(farmer: Farmer, user: User) -> bool:
    if user.role == User.Roles.ADMIN or user.is_superuser:
        return True
    if user.role == User.Roles.FARMER:
        return farmer.user_id == user.id
    return farmer.tenant_id == user.tenant_id and user.tenant_id is not None


def get_farmer_by_phone(phone: str):
    return Farmer.objects.filter(phone=phone).first()


def list_wards(limit=None):
    qs = Ward.objects.all()
    return list(qs[:limit]) if limit else list(qs)


def list_crops():
    return list(Crop.objects.all())


def get_ward_or_404(ward_id):
    try:
        return Ward.objects.get(pk=ward_id)
    except Ward.DoesNotExist as exc:
        raise NotFound("Ward not found.") from exc


def get_crop_or_404(code: str):
    try:
        return Crop.objects.get(code=code)
    except Crop.DoesNotExist as exc:
        raise NotFound(f"Unknown crop code: {code}") from exc


def register_farmer(actor: User, data: dict) -> Farmer:
    """Register a farmer. Consent is mandatory before any record is created."""
    if not data.get("consent_given"):
        raise ValidationError({"consent_given": ["Consent is required before registration."]})

    tenant_id = data.get("tenant_id") or actor.tenant_id
    if actor.role != User.Roles.ADMIN and actor.tenant_id and tenant_id != actor.tenant_id:
        raise ValidationError({"tenant_id": ["You may only register farmers in your tenant."]})

    ward = data["ward"]
    farmer = Farmer.objects.create(
        name=data["name"],
        phone=data["phone"],
        ward=ward,
        tenant_id=tenant_id,
        consent_given=True,
        consent_at=data.get("consent_at") or timezone.now(),
    )
    if data.get("create_login"):
        password = data.get("password")
        if not password:
            raise ValidationError({"password": ["A password is required for a login."]})
        user = User.objects.create_user(
            phone=farmer.phone,
            password=password,
            name=farmer.name,
            role=User.Roles.FARMER,
            tenant_id=tenant_id,
        )
        farmer.user = user
        farmer.save(update_fields=["user"])
    return farmer
