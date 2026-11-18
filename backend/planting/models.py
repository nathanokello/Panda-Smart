from django.db import models

from core.base import UUIDModel
from core.models import Crop, Farmer, Plot, Ward


class AdviceRuleSet(UUIDModel):
    version = models.CharField(max_length=20, unique=True)
    config = models.JSONField(default=dict)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.version


class RainfallObservation(UUIDModel):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="rainfall")
    date = models.DateField()
    rainfall_mm = models.DecimalField(max_digits=8, decimal_places=2)
    source = models.CharField(max_length=50, default="CHIRPS")

    class Meta:
        unique_together = ("ward", "date", "source")
        ordering = ("date",)


class ProduceListing(UUIDModel):
    class Statuses(models.TextChoices):
        AVAILABLE = "available", "Available"
        SOLD = "sold", "Sold"
        CANCELLED = "cancelled", "Cancelled"

    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="produce_listings")
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name="produce_listings")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="produce_listings")
    lot = models.ForeignKey(
        "records.Lot", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="produce_listings",
    )
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=2)
    price_per_kg_kes = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Statuses.choices, default=Statuses.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)


class MarketPrice(UUIDModel):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="prices")
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name="prices")
    date = models.DateField()
    price_per_kg_kes = models.DecimalField(max_digits=10, decimal_places=2)
    source = models.CharField(max_length=50, blank=True, default="KAMIS")

    class Meta:
        unique_together = ("ward", "crop", "date")
        ordering = ("-date",)


class DemandEstimate(UUIDModel):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="demand")
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name="demand")
    season = models.CharField(max_length=50)
    expected_demand_acres = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("ward", "crop", "season")


class Slot(UUIDModel):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="slots")
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, related_name="slots")
    season = models.CharField(max_length=50)
    window_start = models.DateField()
    window_end = models.DateField()
    capacity_acres = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("ward", "crop", "season", "window_start")
        ordering = ("window_start",)


class PlantingIntent(UUIDModel):
    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, related_name="planting_intents")
    plot = models.ForeignKey(
        Plot, null=True, blank=True, on_delete=models.SET_NULL, related_name="intents"
    )
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name="intents")
    acres = models.DecimalField(max_digits=10, decimal_places=2)
    season = models.CharField(max_length=50)
    slot = models.ForeignKey(
        Slot, null=True, blank=True, on_delete=models.SET_NULL, related_name="intents"
    )
    oversubscribed = models.BooleanField(default=False)
    warning = models.TextField(blank=True, default="")
    alternatives = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class UssdSession(models.Model):
    session_id = models.CharField(max_length=100, primary_key=True)
    phone = models.CharField(max_length=20)
    state = models.CharField(max_length=50, blank=True, default="")
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class SeasonRecord(UUIDModel):
    """What a farmer planted in one season and what came of it.

    This is the farmer's own record of past seasons, so they can see what
    worked before instead of repeating the same crop and method by habit.
    """

    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, related_name="season_records")
    plot = models.ForeignKey(
        Plot, null=True, blank=True, on_delete=models.SET_NULL, related_name="season_records"
    )
    season = models.CharField(max_length=50)  # e.g. 2026-long-rains
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name="season_records")
    variety = models.CharField(max_length=100, blank=True, default="")
    acres = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    planted_on = models.DateField(null=True, blank=True)
    methods = models.TextField(blank=True, default="")  # seed, fertiliser, spacing, weeding…
    harvested_on = models.DateField(null=True, blank=True)
    harvest_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    outcome_notes = models.TextField(blank=True, default="")  # drought, pests, late rains…
    recorded_by = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="season_records"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-season", "-created_at")


class SoilTest(UUIDModel):
    """A soil test result the farmer, an agent or an extension officer entered."""

    class Sources(models.TextChoices):
        LAB = "lab", "Laboratory"
        KIT = "kit", "Field test kit"
        EXTENSION = "extension_officer", "Extension officer"
        OTHER = "other", "Other"

    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, related_name="soil_tests")
    plot = models.ForeignKey(
        Plot, null=True, blank=True, on_delete=models.SET_NULL, related_name="soil_tests"
    )
    tested_on = models.DateField()
    source = models.CharField(max_length=30, choices=Sources.choices, default=Sources.LAB)
    ph = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    organic_carbon_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    nitrogen_pct = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    phosphorus_ppm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    potassium_ppm = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="soil_tests"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-tested_on", "-created_at")
