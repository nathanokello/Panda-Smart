from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core import services as core_services
from core.serializers import WardSerializer
from core.models import Farmer, Plot
from planting.models import PlantingIntent


class AdviceQuerySerializer(serializers.Serializer):
    ward = serializers.UUIDField()
    crop = serializers.CharField()

    def validate_crop(self, value):
        return core_services.get_crop_or_404(value)

    def validate_ward(self, value):
        return core_services.get_ward_or_404(value)


class IntentCreateSerializer(serializers.Serializer):
    farmer_id = serializers.UUIDField()
    plot_id = serializers.UUIDField(required=False, allow_null=True)
    crop = serializers.CharField()
    acres = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    season = serializers.CharField(required=False, allow_blank=True)

    def validate_farmer_id(self, value):
        farmer = Farmer.objects.filter(pk=value).first()
        if not farmer:
            raise serializers.ValidationError("Farmer not found.")
        if not farmer.consent_given:
            raise serializers.ValidationError("Farmer consent is required.")
        return farmer

    def validate_crop(self, value):
        return core_services.get_crop_or_404(value)

    def validate_plot_id(self, value):
        if value is None:
            return None
        plot = Plot.objects.filter(pk=value).first()
        if not plot:
            raise serializers.ValidationError("Plot not found.")
        return plot


class SlotRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    window_start = serializers.CharField()
    window_end = serializers.CharField()


class IntentSerializer(serializers.ModelSerializer):
    farmer_id = serializers.UUIDField(source="farmer.id", read_only=True)
    plot_id = serializers.UUIDField(source="plot.id", read_only=True, allow_null=True)
    crop = serializers.CharField(source="crop.code", read_only=True)
    slot = serializers.SerializerMethodField()

    class Meta:
        model = PlantingIntent
        fields = (
            "id",
            "farmer_id",
            "plot_id",
            "crop",
            "acres",
            "season",
            "slot",
            "oversubscribed",
            "warning",
            "alternatives",
            "created_at",
        )

    @extend_schema_field(SlotRefSerializer(allow_null=True))
    def get_slot(self, obj):
        if not obj.slot:
            return None
        return {
            "id": str(obj.slot.id),
            "window_start": obj.slot.window_start.isoformat(),
            "window_end": obj.slot.window_end.isoformat(),
        }


class AdviceResponseSerializer(serializers.Serializer):
    ward = WardSerializer()
    crop = serializers.CharField()
    recommended_window = SlotRefSerializer()
    confidence = serializers.FloatField()
    rationale = serializers.CharField()
    rule_set_version = serializers.CharField()
    alternatives = serializers.ListField(child=serializers.CharField())


class SlotQuerySerializer(serializers.Serializer):
    crop = serializers.CharField()
    season = serializers.CharField(required=False)


class SlotSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    window_start = serializers.CharField()
    window_end = serializers.CharField()
    capacity_acres = serializers.FloatField()
    booked_acres = serializers.FloatField()
    remaining_acres = serializers.FloatField()


class DashboardWardSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    county = serializers.CharField()
    region = serializers.CharField()
    crop_count = serializers.IntegerField()
    total_intended_acres = serializers.FloatField()
    stored_stock_kg = serializers.FloatField()
    generated_at = serializers.DateTimeField()


class DashboardCropSerializer(serializers.Serializer):
    crop = serializers.CharField()
    intended_acres = serializers.FloatField(allow_null=True)
    expected_demand_acres = serializers.FloatField(allow_null=True)
    oversubscription_pct = serializers.FloatField(allow_null=True)
    stored_stock_kg = serializers.FloatField(allow_null=True)
    avg_loss_pct = serializers.FloatField(allow_null=True)
    latest_price_per_kg_kes = serializers.FloatField(allow_null=True)
    sell_flag = serializers.CharField(allow_null=True)
    sell_flag_reason = serializers.CharField()
    suppressed = serializers.BooleanField()


class WardDashboardSerializer(serializers.Serializer):
    ward = WardSerializer()
    generated_at = serializers.DateTimeField()
    crops = DashboardCropSerializer(many=True)


class UssdRequestSerializer(serializers.Serializer):
    sessionId = serializers.CharField()
    phoneNumber = serializers.CharField()
    text = serializers.CharField(required=False, allow_blank=True, default="")
