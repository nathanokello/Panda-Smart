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
