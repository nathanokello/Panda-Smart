"""Pull daily rainfall from NASA POWER for every ward that has coordinates.

    python manage.py fetch_rainfall              # last 60 days, all wards
    python manage.py fetch_rainfall --days 120 --ward "Machakos Town"

Stored as RainfallObservation(source="NASA_POWER"). Re-running updates
existing days. Planting advice uses NASA_POWER data when present (see
RAINFALL_SOURCE_PRIORITY in settings). NASA POWER is about 55 km resolution
and lags a few days behind today.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Ward
from planting.models import RainfallObservation
from planting.weather import WeatherSourceError, fetch_nasa_power_rainfall

SOURCE = "NASA_POWER"


class Command(BaseCommand):
    help = "Fetch daily rainfall for wards from NASA POWER (free, no key)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=60)
        parser.add_argument("--ward", type=str, default="", help="Ward name (default: all wards)")

    def handle(self, *args, **options):
        if options["days"] < 1 or options["days"] > 3660:
            raise CommandError("--days must be between 1 and 3660.")
        end = timezone.localdate()
        start = end - timedelta(days=options["days"])
        wards = Ward.objects.exclude(lat__isnull=True).exclude(lng__isnull=True)
        if options["ward"]:
            wards = wards.filter(name=options["ward"])
        if not wards.exists():
            raise CommandError("No ward with coordinates matches. Set lat and lng on the ward first.")
        total = 0
        for ward in wards:
            try:
                rows = fetch_nasa_power_rainfall(float(ward.lat), float(ward.lng), start, end)
            except WeatherSourceError as exc:
                self.stderr.write(f"{ward}: {exc}")
                continue
            for day, mm in rows:
                RainfallObservation.objects.update_or_create(
                    ward=ward, date=day, source=SOURCE, defaults={"rainfall_mm": Decimal(str(mm))}
                )
            total += len(rows)
            recent = sum(mm for _, mm in rows[-30:])
            self.stdout.write(f"{ward}: {len(rows)} days, {recent:.1f} mm in the latest 30")
        self.stdout.write(self.style.SUCCESS(f"Saved {total} daily rainfall values from NASA POWER."))
