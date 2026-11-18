from django.conf import settings
from django.db import models
from django.utils import timezone
from core.base import UUIDModel


class FarmProfile(UUIDModel):
    """GeoAgri attributes attached to an existing Hifadhi Mavuno Plot."""
    plot = models.OneToOneField("core.Plot", on_delete=models.CASCADE, related_name="geoagri_profile")
    name = models.CharField(max_length=120, blank=True)
    area_unit = models.CharField(max_length=12, choices=(("acres", "Acres"), ("hectares", "Hectares")), default="acres")
    irrigation_status = models.CharField(max_length=20, choices=(("irrigated", "Irrigated"), ("rainfed", "Rain-fed"), ("partial", "Partially irrigated"), ("unknown", "Unknown")), default="unknown")
    water_availability = models.CharField(max_length=20, choices=(("reliable", "Reliable"), ("seasonal", "Seasonal"), ("limited", "Limited"), ("unknown", "Unknown")), default="unknown")
    soil_type = models.CharField(max_length=80, blank=True)
    current_crops = models.JSONField(default=list, blank=True)
    boundary_geojson = models.JSONField(null=True, blank=True)
    location_consent = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.location_consent and not self.consent_at:
            self.consent_at = timezone.now()
        if not self.location_consent:
            self.consent_at = None
        super().save(*args, **kwargs)


class EnvironmentalObservation(UUIDModel):
    plot = models.ForeignKey("core.Plot", on_delete=models.CASCADE, related_name="environmental_observations")
    variable = models.CharField(max_length=60)
    value = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    source = models.CharField(max_length=100)
    observed_at = models.DateTimeField()
    spatial_resolution = models.CharField(max_length=80, blank=True)
    quality = models.CharField(max_length=20, choices=(("high", "High"), ("medium", "Medium"), ("low", "Low"), ("unknown", "Unknown")), default="unknown")
    confidence = models.FloatField(null=True, blank=True)
    uncertainty_note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-observed_at",)
        indexes = [models.Index(fields=("plot", "variable", "observed_at"))]


class CropRequirement(UUIDModel):
    """Only populated with thresholds supported by cited agronomic sources."""
    crop_code = models.CharField(max_length=30, db_index=True)
    crop_name = models.CharField(max_length=100)
    variable = models.CharField(max_length=60)
    minimum = models.FloatField(null=True, blank=True)
    maximum = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    source_name = models.CharField(max_length=160)
    source_url = models.URLField(blank=True)
    source_version = models.CharField(max_length=80, blank=True)
    region = models.CharField(max_length=100, default="Kenya")
    notes = models.TextField(blank=True)
    verified = models.BooleanField(default=False)

    class Meta:
        unique_together = ("crop_code", "variable", "region", "source_name")


class SuitabilityAssessment(UUIDModel):
    plot = models.ForeignKey("core.Plot", on_delete=models.CASCADE, related_name="suitability_assessments")
    crop_code = models.CharField(max_length=30)
    crop_name = models.CharField(max_length=100)
    classification = models.CharField(max_length=20, choices=(("suitable", "Suitable"), ("moderate", "Moderately suitable"), ("unsuitable", "Unsuitable"), ("insufficient_data", "Insufficient data")))
    score = models.FloatField(null=True, blank=True)
    explanation = models.JSONField(default=dict, blank=True)
    assessed_at = models.DateTimeField(auto_now_add=True)
    engine_version = models.CharField(max_length=30, default="rules-0.1")


class FarmConsent(UUIDModel):
    plot = models.ForeignKey("core.Plot", on_delete=models.CASCADE, related_name="geoagri_consents")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=80)
    granted = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    policy_version = models.CharField(max_length=30, default="1.0")


class RegionalPlantingIntent(UUIDModel):
    plot = models.ForeignKey("core.Plot", on_delete=models.CASCADE, related_name="regional_intents")
    crop_code = models.CharField(max_length=30)
    expected_planting_date = models.DateField(null=True, blank=True)
    expected_quantity_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    share_for_aggregation = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
