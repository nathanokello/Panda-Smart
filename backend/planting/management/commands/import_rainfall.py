"""Import CHIRPS-style rainfall CSV files: ward_name,date,rainfall_mm,source."""
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import Ward
from planting.models import RainfallObservation


class Command(BaseCommand):
    help = "Import rainfall observations from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)

    def handle(self, *args, **options):
        path = Path(options["csv_file"])
        if not path.exists():
            raise CommandError(f"CSV file not found: {path}")
        created = 0
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required = {"ward_name", "date", "rainfall_mm"}
            if not required.issubset(reader.fieldnames or []):
                raise CommandError(f"CSV must have columns: {', '.join(sorted(required))}")
            for row in reader:
                ward = Ward.objects.filter(name=row["ward_name"]).first()
                if not ward:
                    self.stderr.write(f"Skipping unknown ward: {row['ward_name']}")
                    continue
                _, was_created = RainfallObservation.objects.get_or_create(
                    ward=ward,
                    date=date.fromisoformat(row["date"]),
                    source=row.get("source") or "CHIRPS",
                    defaults={"rainfall_mm": Decimal(row["rainfall_mm"])},
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Imported {created} new rainfall observations."))
