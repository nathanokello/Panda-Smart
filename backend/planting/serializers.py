from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core import services as core_services
from core.serializers import WardSerializer
from core.models import Farmer, Plot
from planting.history import soil_guidance, yield_per_acre
from planting.models import PlantingIntent, ProduceListing, SeasonRecord, SoilTest


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


class WindowSerializer(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()


class ProduceListingSerializer(serializers.ModelSerializer):
    farmer_id = serializers.UUIDField(source="farmer.id", read_only=True)
    farmer_name = serializers.CharField(source="farmer.name", read_only=True)
    crop = serializers.CharField(source="crop.code", read_only=True)
    ward = serializers.CharField(source="ward.name", read_only=True)
    county = serializers.CharField(source="ward.county", read_only=True)
    lot_id = serializers.UUIDField(source="lot.id", read_only=True, allow_null=True)

    class Meta:
        model = ProduceListing
        fields = (
            "id", "farmer_id", "farmer_name", "crop", "ward", "county", "lot_id",
            "quantity_kg", "price_per_kg_kes", "description", "status",
            "created_at", "updated_at",
        )


class ProduceListingCreateSerializer(serializers.Serializer):
    crop = serializers.CharField()
    quantity_kg = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    price_per_kg_kes = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    lot_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_crop(self, value):
        return core_services.get_crop_or_404(value)


class ProduceListingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["available", "sold", "cancelled"])


class AdviceResponseSerializer(serializers.Serializer):
    ward = WardSerializer()
    crop = serializers.CharField()
    # The engine returns {"start", "end"} (architecture.md 6.3), not a slot.
    recommended_window = WindowSerializer()
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


# ---- Season history and soil records ----


class SeasonRecordSerializer(serializers.ModelSerializer):
    farmer_id = serializers.UUIDField(source="farmer.id", read_only=True)
    plot_id = serializers.UUIDField(source="plot.id", read_only=True, allow_null=True)
    crop = serializers.CharField(source="crop.code", read_only=True)
    yield_kg_per_acre = serializers.SerializerMethodField()
    recorded_by = serializers.SerializerMethodField()

    class Meta:
        model = SeasonRecord
        fields = ("id", "farmer_id", "plot_id", "season", "crop", "variety", "acres", "planted_on",
                  "methods", "harvested_on", "harvest_kg", "yield_kg_per_acre", "outcome_notes",
                  "recorded_by", "created_at", "updated_at")

    def get_yield_kg_per_acre(self, obj) -> float | None:
        return yield_per_acre(obj)

    def get_recorded_by(self, obj) -> str | None:
        return obj.recorded_by.name if obj.recorded_by else None


class SeasonRecordWriteSerializer(serializers.Serializer):
    plot_id = serializers.UUIDField(required=False, allow_null=True)
    season = serializers.RegexField(r"^\d{4}-[a-z0-9-]{2,40}$", max_length=50,
                                    error_messages={"invalid": "Use a form like 2026-long-rains."})
    crop = serializers.CharField()
    variety = serializers.CharField(max_length=100, required=False, allow_blank=True)
    acres = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"),
                                     required=False, allow_null=True)
    planted_on = serializers.DateField(required=False, allow_null=True)
    methods = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    harvested_on = serializers.DateField(required=False, allow_null=True)
    harvest_kg = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"),
                                          required=False, allow_null=True)
    outcome_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_crop(self, value):
        return core_services.get_crop_or_404(value)

    def validate(self, attrs):
        farmer = self.context["farmer"]
        plot_id = attrs.pop("plot_id", None)
        if plot_id:
            plot = Plot.objects.filter(pk=plot_id, farmer=farmer).first()
            if not plot:
                raise serializers.ValidationError({"plot_id": ["Plot not found for this farmer."]})
            attrs["plot"] = plot
        elif "plot_id" in self.initial_data:
            attrs["plot"] = None
        planted = attrs.get("planted_on", getattr(self.instance, "planted_on", None))
        harvested = attrs.get("harvested_on", getattr(self.instance, "harvested_on", None))
        if planted and harvested and harvested < planted:
            raise serializers.ValidationError({"harvested_on": ["Harvest date is before planting date."]})
        return attrs


class SoilTestSerializer(serializers.ModelSerializer):
    farmer_id = serializers.UUIDField(source="farmer.id", read_only=True)
    plot_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    plot = serializers.UUIDField(source="plot.id", read_only=True, allow_null=True)
    guidance = serializers.SerializerMethodField()
    recorded_by = serializers.SerializerMethodField()
    ph = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=Decimal("2"),
                                  max_value=Decimal("11"), required=False, allow_null=True)
    organic_carbon_pct = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"),
                                                  max_value=Decimal("60"), required=False, allow_null=True)
    nitrogen_pct = serializers.DecimalField(max_digits=5, decimal_places=3, min_value=Decimal("0"),
                                            max_value=Decimal("10"), required=False, allow_null=True)
    phosphorus_ppm = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0"),
                                              required=False, allow_null=True)
    potassium_ppm = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0"),
                                             required=False, allow_null=True)

    class Meta:
        model = SoilTest
        fields = ("id", "farmer_id", "plot_id", "plot", "tested_on", "source", "ph",
                  "organic_carbon_pct", "nitrogen_pct", "phosphorus_ppm", "potassium_ppm",
                  "notes", "guidance", "recorded_by", "created_at")
        read_only_fields = ("id", "created_at")

    def get_guidance(self, obj) -> list:
        return soil_guidance(obj)

    def get_recorded_by(self, obj) -> str | None:
        return obj.recorded_by.name if obj.recorded_by else None

    def validate(self, attrs):
        measured = ("ph", "organic_carbon_pct", "nitrogen_pct", "phosphorus_ppm", "potassium_ppm")
        if all(attrs.get(name) is None for name in measured):
            raise serializers.ValidationError({"ph": ["Enter at least one measured value."]})
        plot_id = attrs.pop("plot_id", None)
        if plot_id:
            plot = Plot.objects.filter(pk=plot_id, farmer=self.context["farmer"]).first()
            if not plot:
                raise serializers.ValidationError({"plot_id": ["Plot not found for this farmer."]})
            attrs["plot"] = plot
        return attrs
