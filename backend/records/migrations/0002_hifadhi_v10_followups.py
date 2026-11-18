from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("records", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="lot",
            name="moisture_status",
            field=models.CharField(
                choices=[
                    ("unknown", "Limit not confirmed"),
                    ("dry", "Dry enough"),
                    ("retest", "Needs re-test"),
                    ("officer", "Extension officer needed"),
                ],
                default="unknown",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="lot",
            name="retest_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="lot",
            name="next_check_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ScheduledCheck",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ("kind", models.CharField(
                    choices=[("retest", "Moisture re-test"), ("checkup", "Storage check-up")],
                    max_length=20,
                )),
                ("due_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
                ("moisture_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("good_weight_kg", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("pests", models.BooleanField(blank=True, null=True)),
                ("lot", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="scheduled_checks",
                    to="records.lot",
                )),
            ],
            options={"ordering": ("due_at",)},
        ),
    ]
