import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("planting", "0002_seasonrecord_soiltest"),
        ("records", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProduceListing",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("quantity_kg", models.DecimalField(decimal_places=2, max_digits=12)),
                ("price_per_kg_kes", models.DecimalField(decimal_places=2, max_digits=10)),
                ("description", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("available", "Available"), ("sold", "Sold"), ("cancelled", "Cancelled")], default="available", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("crop", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="produce_listings", to="core.crop")),
                ("farmer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="produce_listings", to="core.farmer")),
                ("lot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="produce_listings", to="records.lot")),
                ("ward", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="produce_listings", to="core.ward")),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
