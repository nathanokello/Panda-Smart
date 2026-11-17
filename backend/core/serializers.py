from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.validators import UniqueValidator

from core.models import Crop, Farmer, Plot, Tenant, User, Ward


class UserSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = ("id", "phone", "name", "role", "tenant_id")


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(phone=attrs["phone"], password=attrs["password"])
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
    phone = serializers.CharField(
        max_length=20, validators=[UniqueValidator(queryset=Farmer.objects.all())]
    )
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all())
    consent_given = serializers.BooleanField()
    consent_at = serializers.DateTimeField(required=False, allow_null=True)
    create_login = serializers.BooleanField(default=False)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs.get("create_login") and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": ["A password is required when create_login is true."]}
            )
        return attrs
