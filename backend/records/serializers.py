from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core import services as core_services
from core.models import Farmer
from records import services
from records.models import Lot, LotEvent


class LotRegisterSerializer(serializers.Serializer):
    farmer_id = serializers.UUIDField()
    crop = serializers.CharField()
    weight_kg = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    bag_count = serializers.IntegerField(min_value=0)
    storage_method = serializers.CharField()
    location_label = serializers.CharField()
    moisture_pct = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        allow_null=True,
    )

    def validate_farmer_id(self, value):
        farmer = Farmer.objects.filter(pk=value).first()
        if not farmer:
            raise serializers.ValidationError("Farmer not found.")
        if not farmer.consent_given:
            raise serializers.ValidationError("Farmer consent is required.")
        return farmer

    def validate_crop(self, value):
        return core_services.get_crop_or_404(value)

    def validate(self, attrs):
        user = self.context["request"].user
        if not core_services.farmer_is_visible(attrs["farmer_id"], user):
            raise serializers.ValidationError(
                {"farmer_id": ["You may only register lots for your tenant."]}
            )
        return attrs


class AgentRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class LotSummarySerializer(serializers.Serializer):
    latest_weight_kg = serializers.FloatField()
    loss_kg = serializers.FloatField()
    loss_pct = serializers.FloatField()
    latest_moisture_pct = serializers.FloatField(allow_null=True)


class LotSerializer(serializers.ModelSerializer):
    crop = serializers.CharField(source="crop.code", read_only=True)
    farmer_id = serializers.UUIDField(source="farmer.id", read_only=True)
    ward_id = serializers.UUIDField(source="ward.id", read_only=True)
    agent = serializers.SerializerMethodField()
    verification_url = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = Lot
        fields = (
            "id",
            "crop",
            "status",
            "initial_weight_kg",
            "registered_at",
            "location_label",
            "farmer_id",
            "ward_id",
            "agent",
            "verification_url",
            "summary",
        )

    @extend_schema_field(AgentRefSerializer)
    def get_agent(self, obj):
        return {"id": str(obj.agent_id), "name": obj.agent.name}

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_verification_url(self, obj):
        token = obj.verification_tokens.order_by("-created_at").first()
        return services.verification_url(token) if token else None

    @extend_schema_field(LotSummarySerializer)
    def get_summary(self, obj):
        return services.get_summary(obj)


class LotEventSerializer(serializers.ModelSerializer):
    recorded_by = serializers.SerializerMethodField()

    class Meta:
        model = LotEvent
        fields = ("id", "type", "payload", "recorded_by", "recorded_at", "hash", "sequence")

    @extend_schema_field(AgentRefSerializer(allow_null=True))
    def get_recorded_by(self, obj):
        if not obj.recorded_by:
            return None
        return {"id": str(obj.recorded_by_id), "name": obj.recorded_by.name}


class EventCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=LotEvent.Types.choices)
    payload = serializers.JSONField()

    def validate(self, attrs):
        services.validate_event_payload(
            attrs["type"], attrs["payload"], lot=self.context.get("lot")
        )
        return attrs


class VerifyChainResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()


class VerifyEventSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    type = serializers.CharField()
    recorded_at = serializers.DateTimeField()
    payload = serializers.JSONField()


class VerifyDataSerializer(serializers.Serializer):
    lot = serializers.DictField()
    farmer_name = serializers.CharField()
    events = VerifyEventSerializer(many=True)
    summary = LotSummarySerializer()
    already_responded = serializers.BooleanField()


class DisputeRequestSerializer(serializers.Serializer):
    reason = serializers.CharField()


class VerifyActionResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    status = serializers.CharField()
