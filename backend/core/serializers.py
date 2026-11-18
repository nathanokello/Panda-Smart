from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from core.models import Crop, Farmer, Plot, Tenant, User, Ward
from core.phone import is_valid_phone, normalize_phone


def clean_new_phone(value):
    """Normalise a phone number for a new account and check it is unused."""
    phone = normalize_phone(value)
    if not is_valid_phone(phone):
        raise serializers.ValidationError(
            "Enter a phone number such as 0712345678 or +254712345678."
        )
    if User.objects.filter(phone=phone).exists() or Farmer.objects.filter(phone=phone).exists():
        raise serializers.ValidationError("An account with this phone number already exists.")
    return phone


class UserSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True, allow_null=True)
    # Lets a signed-in farmer load their own farmer record and plots.
    farmer_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "phone", "name", "role", "tenant_id", "farmer_id")

    def get_farmer_id(self, obj) -> str | None:
        profile = getattr(obj, "farmer_profile", None)
        return str(profile.id) if profile else None


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone = normalize_phone(attrs["phone"])
        user = authenticate(phone=phone, password=attrs["password"])
        if user is None and phone != attrs["phone"].strip():
            # Accounts created before normalisation may be stored as typed.
            user = authenticate(phone=attrs["phone"].strip(), password=attrs["password"])
        if not user or not user.is_active:
            raise AuthenticationFailed({"detail": "Invalid phone or password."})
        attrs["user"] = user
        return attrs


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()


class TokenResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    user = UserSerializer()


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ("id", "name", "type")


class WardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ward
        fields = ("id", "name", "county", "region", "lat", "lng")


class CropSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = ("id", "code", "name_en", "name_sw", "storable")


class PlotSerializer(serializers.ModelSerializer):
    farmer_id = serializers.UUIDField(source="farmer.id", read_only=True)
    ward_id = serializers.UUIDField(source="ward.id", read_only=True)

    class Meta:
        model = Plot
        fields = ("id", "farmer_id", "ward_id", "acres", "lat", "lng", "created_at")


class PlotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plot
        fields = ("id", "ward", "acres", "lat", "lng")


class FarmerSerializer(serializers.ModelSerializer):
    ward = WardSerializer(read_only=True)
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True, allow_null=True)
    plots = PlotSerializer(many=True, read_only=True)

    class Meta:
        model = Farmer
        fields = (
            "id",
            "name",
            "phone",
            "ward",
            "tenant_id",
            "consent_given",
            "consent_at",
            "plots",
            "created_at",
        )


class FarmerCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20)
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all())
    consent_given = serializers.BooleanField()
    consent_at = serializers.DateTimeField(required=False, allow_null=True)
    create_login = serializers.BooleanField(default=False)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate_phone(self, value):
        return clean_new_phone(value)

    def validate(self, attrs):
        if attrs.get("create_login") and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": ["A password is required when create_login is true."]}
            )
        return attrs


class FarmerSelfRegisterSerializer(serializers.Serializer):
    """Public farmer sign-up. The role is always forced to farmer server-side."""

    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, min_length=8)
    ward_id = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all())
    consent_given = serializers.BooleanField()

    def validate_phone(self, value):
        return clean_new_phone(value)

    def validate_consent_given(self, value):
        if not value:
            raise serializers.ValidationError("Consent is required before registration.")
        return value

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password

        validate_password(value)
        return value


class StaffUserSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True, allow_null=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True, allow_null=True)
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "phone", "name", "role", "tenant_id", "tenant_name", "is_active",
                  "date_joined", "last_login", "can_manage")

    def get_can_manage(self, obj) -> bool:
        from core.services import can_manage

        request = self.context.get("request")
        return bool(request and can_manage(request.user, obj))


STAFF_ROLE_CHOICES = [
    (User.Roles.AGENT, "Storage agent"),
    (User.Roles.COOP_ADMIN, "Cooperative admin"),
    (User.Roles.ADMIN, "Administrator"),
]


class StaffUserCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20)
    role = serializers.ChoiceField(choices=STAFF_ROLE_CHOICES)
    tenant_id = serializers.PrimaryKeyRelatedField(
        queryset=Tenant.objects.all(), required=False, allow_null=True, source="tenant"
    )
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_phone(self, value):
        return clean_new_phone(value)


class StaffUserUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    role = serializers.ChoiceField(choices=STAFF_ROLE_CHOICES, required=False)
    tenant_id = serializers.PrimaryKeyRelatedField(
        queryset=Tenant.objects.all(), required=False, allow_null=True, source="tenant"
    )
    is_active = serializers.BooleanField(required=False)
    password = serializers.CharField(write_only=True, min_length=8, required=False)
