"""Shared service functions.

Other apps call these instead of importing core models into their views.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from core.models import Crop, Farmer, Tenant, User, Ward


def tenant_scope(user: User):
    """Return the tenant id the user may see, or None for unrestricted admins."""
    if not user or not user.is_authenticated:
        return None
    if user.role == User.Roles.ADMIN or user.is_superuser:
        return None
    return user.tenant_id


def farmers_for_user(user: User):
    qs = Farmer.objects.select_related("ward", "tenant")
    if not user or not user.is_authenticated:
        return qs.none()
    if user.role == User.Roles.ADMIN or user.is_superuser:
        return qs
    if user.role == User.Roles.FARMER:
        # A farmer reaches only their own record, whether or not they have a cooperative.
        return qs.filter(user_id=user.id)
    if user.tenant_id is None:
        # Previously a non-admin with no cooperative got an unfiltered queryset,
        # i.e. every farmer in the system.
        return qs.none()
    return qs.filter(tenant_id=user.tenant_id)


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


@transaction.atomic
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
        # Same password rules as every other account.
        _check_password(password, User(phone=farmer.phone, name=farmer.name))
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


def default_self_register_tenant():
    """Tenant for self-registered farmers, so their cooperative's agents can see them.

    Uses SELF_REGISTER_TENANT (a tenant name) when set, otherwise the oldest
    cooperative. Returns None when no tenant exists yet.
    """
    name = getattr(settings, "SELF_REGISTER_TENANT", "")
    if name:
        tenant = Tenant.objects.filter(name=name).first()
        if tenant:
            return tenant
    return (
        Tenant.objects.filter(type=Tenant.Types.COOPERATIVE).order_by("created_at").first()
    )


@transaction.atomic
def self_register_farmer(data: dict):
    """Create a farmer login and farmer record from the public sign-up form."""
    if not data.get("consent_given"):
        raise ValidationError({"consent_given": ["Consent is required before registration."]})
    tenant = default_self_register_tenant()
    user = User.objects.create_user(
        phone=data["phone"],
        password=data["password"],
        name=data["name"],
        role=User.Roles.FARMER,
        tenant=tenant,
    )
    farmer = Farmer.objects.create(
        user=user,
        name=data["name"],
        phone=data["phone"],
        ward=data["ward_id"],
        tenant=tenant,
        consent_given=True,
        consent_at=timezone.now(),
    )
    return user, farmer


# ---------------------------------------------------------------------------
# Staff user management (users.html)
# ---------------------------------------------------------------------------
# Which roles each role may create and manage. Coop admins manage agents in
# their own cooperative only. Change this table, not the views, if the team
# decides otherwise. Farmers are managed through /farmers/, not here.
MANAGEABLE_ROLES = {
    User.Roles.ADMIN: (User.Roles.AGENT, User.Roles.COOP_ADMIN, User.Roles.ADMIN),
    User.Roles.COOP_ADMIN: (User.Roles.AGENT,),
}
STAFF_ROLE_VALUES = (User.Roles.AGENT, User.Roles.COOP_ADMIN, User.Roles.ADMIN)


def _check_password(password: str, user: User):
    """Django's password checks raise a Django error; turn it into a 400."""
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": list(exc.messages)}) from exc


def _is_admin(user: User) -> bool:
    return user.role == User.Roles.ADMIN or user.is_superuser


def staff_users_for(actor: User):
    """Staff accounts the actor may see. Coop admins see their own cooperative."""
    qs = User.objects.filter(role__in=STAFF_ROLE_VALUES).select_related("tenant").order_by("name")
    if _is_admin(actor):
        return qs
    return qs.filter(tenant_id=actor.tenant_id) if actor.tenant_id else qs.none()


def can_manage(actor: User, target: User) -> bool:
    if target.pk == actor.pk:
        return False  # nobody changes their own role or status here
    allowed = MANAGEABLE_ROLES.get(User.Roles.ADMIN if _is_admin(actor) else actor.role, ())
    if target.role not in allowed:
        return False
    return _is_admin(actor) or bool(actor.tenant_id and target.tenant_id == actor.tenant_id)


def tenants_for(actor: User):
    if _is_admin(actor):
        return Tenant.objects.order_by("name")
    return Tenant.objects.filter(pk=actor.tenant_id)


@transaction.atomic
def create_staff_user(actor: User, data: dict) -> User:
    role = data["role"]
    allowed = MANAGEABLE_ROLES.get(User.Roles.ADMIN if _is_admin(actor) else actor.role, ())
    if role not in allowed:
        raise ValidationError({"role": [f"You may not create {role} accounts."]})
    tenant = data.get("tenant")
    if not _is_admin(actor):
        tenant = actor.tenant  # coop admins always create inside their cooperative
    if role != User.Roles.ADMIN and tenant is None:
        raise ValidationError({"tenant_id": ["Agents and cooperative admins need a cooperative."]})
    user = User(phone=data["phone"], name=data["name"], role=role, tenant=tenant)
    _check_password(data["password"], user)
    user.set_password(data["password"])
    user.save()
    return user


@transaction.atomic
def update_staff_user(actor: User, target: User, data: dict) -> User:
    """Change name, active status, password, role or cooperative. Never deletes."""
    from rest_framework.authtoken.models import Token
    from rest_framework.exceptions import PermissionDenied

    if not can_manage(actor, target):
        raise PermissionDenied("You may not change this account.")
    fields = []
    revoke = False
    if "name" in data:
        target.name = data["name"]
        fields.append("name")
    if "role" in data and data["role"] != target.role:
        allowed = MANAGEABLE_ROLES.get(User.Roles.ADMIN if _is_admin(actor) else actor.role, ())
        if data["role"] not in allowed:
            raise ValidationError({"role": [f"You may not give the {data['role']} role."]})
        target.role = data["role"]
        fields.append("role")
        revoke = True
    if "tenant" in data and _is_admin(actor):
        target.tenant = data["tenant"]
        fields.append("tenant")
        revoke = True
    if "is_active" in data and data["is_active"] != target.is_active:
        target.is_active = data["is_active"]
        fields.append("is_active")
        revoke = revoke or not data["is_active"]
    if data.get("password"):
        _check_password(data["password"], target)
        target.set_password(data["password"])
        fields.append("password")
        revoke = True
    if target.role != User.Roles.ADMIN and target.tenant_id is None:
        raise ValidationError({"tenant_id": ["Agents and cooperative admins need a cooperative."]})
    if fields:
        target.save(update_fields=fields)
    if revoke:
        # Sign the account out everywhere after a status, role or password change.
        Token.objects.filter(user=target).delete()
    return target
