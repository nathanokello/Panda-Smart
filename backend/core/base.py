import uuid

from django.db import models


class UUIDModel(models.Model):
    """Shared UUID primary key (architecture.md Section 4)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
