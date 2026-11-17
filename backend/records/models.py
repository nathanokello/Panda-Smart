import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.base import UUIDModel
from core.models import Crop, Farmer, User, Ward
from records.hashing import compute_hash


class AppendOnlyError(Exception):
    """Raised when code tries to update or delete a lot event."""


def generate_verification_token() -> str:
    return secrets.token_urlsafe(24)


def default_verification_expiry():
    return timezone.now() + timedelta(days=settings.VERIFY_TOKEN_TTL_DAYS)


class Lot(UUIDModel):
    class Statuses(models.TextChoices):
        STORED = "stored", "Stored"
        SOLD = "sold", "Sold"
        DISPUTED = "disputed", "Disputed"
        CLOSED = "closed", "Closed"

    farmer = models.ForeignKey(Farmer, on_delete=models.PROTECT, related_name="lots")
    agent = models.ForeignKey(User, on_delete=models.PROTECT, related_name="registered_lots")
    crop = models.ForeignKey(Crop, on_delete=models.PROTECT, related_name="lots")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="lots")
    initial_weight_kg = models.DecimalField(max_digits=12, decimal_places=2)
    location_label = models.CharField(max_length=200)
    registered_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=Statuses.choices, default=Statuses.STORED)

    class Meta:
        ordering = ("-registered_at",)

    def __str__(self):
        return f"{self.crop.code} lot - {self.farmer.name}"


class LotEvent(UUIDModel):
    class Types(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        MOISTURE_READING = "MOISTURE_READING", "Moisture reading"
        WEIGHT_READING = "WEIGHT_READING", "Weight reading"
        CHECKUP = "CHECKUP", "Check-up"
        LOSS_RECORDED = "LOSS_RECORDED", "Loss recorded"
        VERIFIED = "VERIFIED", "Verified by farmer"
        DISPUTED = "DISPUTED", "Disputed by farmer"
        CORRECTION = "CORRECTION", "Correction"

    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="events")
    type = models.CharField(max_length=30, choices=Types.choices)
    payload = models.JSONField(default=dict)
    recorded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="recorded_events"
    )
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    sequence = models.PositiveIntegerField()
    prev_hash = models.CharField(max_length=64, blank=True, default="")
    hash = models.CharField(max_length=64, editable=False)

    class Meta:
        ordering = ("sequence",)
        unique_together = ("lot", "sequence")

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise AppendOnlyError("Lot events are append-only; add a CORRECTION event instead.")
        if not self.hash:
            self.hash = compute_hash(self.prev_hash, self.type, self.payload, self.recorded_at)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("Lot events are append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.type} #{self.sequence} - {self.lot_id}"


class VerificationToken(UUIDModel):
    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="verification_tokens")
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="verification_tokens")
    token = models.CharField(max_length=64, unique=True, default=generate_verification_token)
    expires_at = models.DateTimeField(default=default_verification_expiry)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Verify token for {self.lot_id}"
