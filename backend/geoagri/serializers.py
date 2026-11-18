from rest_framework import serializers
from django.utils import timezone
from core.models import Plot, Ward
from .models import FarmProfile, EnvironmentalObservation, RegionalPlantingIntent, FarmConsent

class FarmSerializer(serializers.ModelSerializer):
    plot_id = serializers.UUIDField(source="plot.id", read_only=True)
    farmer_id = serializers.UUIDField(source="plot.farmer_id", read_only=True)
    ward_id = serializers.UUIDField(source="plot.ward_id", read_only=True)
    acres = serializers.DecimalField(source="plot.acres", max_digits=10, decimal_places=2)
    lat = serializers.DecimalField(source="plot.lat", max_digits=9, decimal_places=6, required=False, allow_null=True)
    lng = serializers.DecimalField(source="plot.lng", max_digits=9, decimal_places=6, required=False, allow_null=True)
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all(), write_only=True, required=False)
    class Meta:
        model = FarmProfile
        fields = ("id", "plot_id", "farmer_id", "ward_id", "ward", "acres", "lat", "lng", "name", "area_unit", "irrigation_status", "water_availability", "soil_type", "current_crops", "boundary_geojson", "location_consent", "consent_at", "updated_at")
        read_only_fields = ("id", "plot_id", "farmer_id", "ward_id", "consent_at", "updated_at")

    def validate(self, attrs):
        boundary = attrs.get("boundary_geojson")
        if boundary:
            if boundary.get("type") not in ("Polygon", "MultiPolygon") or not isinstance(boundary.get("coordinates"), list):
                raise serializers.ValidationError({"boundary_geojson": "Provide a valid GeoJSON Polygon or MultiPolygon."})
        plot_attrs = attrs.get("plot", {})
        has_lat = plot_attrs.get("lat", getattr(getattr(self.instance, "plot", None), "lat", None)) is not None
        if attrs.get("location_consent") and not has_lat:
            raise serializers.ValidationError({"location_consent": "A farm location is required before consenting to location processing."})
        return attrs

    def create(self, validated_data):
        plot_data = validated_data.pop("plot", {})
        ward = validated_data.pop("ward", None)
        if ward is not None: plot_data["ward"] = ward
        request = self.context["request"]
        farmer = getattr(request.user, "farmer_profile", None)
        if not farmer:
            raise serializers.ValidationError("This account is not linked to a farmer profile.")
        if "ward" not in plot_data:
            plot_data["ward"] = farmer.ward
        plot = Plot.objects.create(farmer=farmer, **plot_data)
        profile = FarmProfile.objects.create(plot=plot, **validated_data)
        if profile.location_consent:
            FarmConsent.objects.create(plot=plot, user=request.user, purpose="farm_location_intelligence", granted=True)
        return profile

    def update(self, instance, validated_data):
        plot_data = validated_data.pop("plot", {})
        ward = validated_data.pop("ward", None)
        if ward is not None: plot_data["ward"] = ward
        for key, value in plot_data.items(): setattr(instance.plot, key, value)
        if plot_data: instance.plot.save()
        previous_consent = instance.location_consent
        updated = super().update(instance, validated_data)
        if "location_consent" in self.initial_data and previous_consent != updated.location_consent:
            FarmConsent.objects.create(plot=instance.plot, user=self.context["request"].user, purpose="farm_location_intelligence", granted=updated.location_consent, revoked_at=None if updated.location_consent else timezone.now())
        return updated

class EnvironmentalObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnvironmentalObservation
        fields = ("id", "variable", "value", "unit", "source", "observed_at", "spatial_resolution", "quality", "confidence", "uncertainty_note", "fetched_at")

class RegionalIntentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegionalPlantingIntent
        fields = ("id", "crop_code", "expected_planting_date", "expected_quantity_kg", "share_for_aggregation", "created_at")
