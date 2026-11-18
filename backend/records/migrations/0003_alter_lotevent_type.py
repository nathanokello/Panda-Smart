from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("records", "0002_hifadhi_v10_followups"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lotevent",
            name="type",
            field=models.CharField(
                choices=[
                    ("REGISTERED", "Registered"),
                    ("MOISTURE_READING", "Moisture reading"),
                    ("WEIGHT_READING", "Weight reading"),
                    ("CHECKUP", "Check-up"),
                    ("LOSS_RECORDED", "Loss recorded"),
                    ("VERIFIED", "Verified by farmer"),
                    ("DISPUTED", "Disputed by farmer"),
                    ("CORRECTION", "Correction"),
                    ("SYSTEM_DECISION", "System moisture decision"),
                ],
                max_length=30,
            ),
        ),
    ]
