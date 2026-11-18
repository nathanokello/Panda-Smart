# Written by hand to match planting/models.py (SeasonRecord, SoilTest).
# If `python manage.py makemigrations --check` reports changes, run
# `python manage.py makemigrations planting` and keep the generated file instead.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("planting", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SeasonRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("season", models.CharField(max_length=50)),
                ("variety", models.CharField(blank=True, default="", max_length=100)),
                ("acres", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("planted_on", models.DateField(blank=True, null=True)),
                ("methods", models.TextField(blank=True, default="")),
                ("harvested_on", models.DateField(blank=True, null=True)),
                ("harvest_kg", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("outcome_notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("crop", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="season_records", to="core.crop")),
                ("farmer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="season_records", to="core.farmer")),
                ("plot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="season_records", to="core.plot")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="season_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-season", "-created_at")},
        ),
        migrations.CreateModel(
            name="SoilTest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tested_on", models.DateField()),
                ("source", models.CharField(choices=[("lab", "Laboratory"), ("kit", "Field test kit"), ("extension_officer", "Extension officer"), ("other", "Other")], default="lab", max_length=30)),
                ("ph", models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ("organic_carbon_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("nitrogen_pct", models.DecimalField(blank=True, decimal_places=3, max_digits=5, null=True)),
                ("phosphorus_ppm", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ("potassium_ppm", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("farmer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="soil_tests", to="core.farmer")),
                ("plot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="soil_tests", to="core.plot")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="soil_tests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-tested_on", "-created_at")},
        ),
    ]
