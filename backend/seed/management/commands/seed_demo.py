"""Create the MVP demo dataset described in architecture.md Section 11.

Safe to run more than once: base records are matched by their natural keys and
lots/intents are only created when their tables are empty.
"""
import csv
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Crop, Farmer, Plot, Tenant, User, Ward
from planting import services as planting_services
from planting.models import (
    AdviceRuleSet,
    DemandEstimate,
    MarketPrice,
    RainfallObservation,
    Slot,
)
from planting.rules.engine import load_file_config
from records import services as records_services

SEASON = "2026-short-rains"
PASSWORD = "demo1234"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

WARDS = [
    ("Kitui Central", "Kitui", Ward.Regions.SOUTH_EASTERN, "-1.3678", "38.0103"),
    ("Makueni Town", "Makueni", Ward.Regions.SOUTH_EASTERN, "-1.8026", "37.2740"),
    ("Machakos Town", "Machakos", Ward.Regions.SOUTH_EASTERN, "-1.5177", "37.2633"),
    ("Kibwezi", "Makueni", Ward.Regions.SOUTH_EASTERN, "-2.4067", "37.9634"),
    ("Westlands", "Nairobi", Ward.Regions.METROPOLITAN, "-1.0560", "36.8000"),
    ("Mombasa Island", "Mombasa", Ward.Regions.METROPOLITAN, "-4.0435", "39.6682"),
]
CROPS = [
    ("maize", "Maize", "Mahindi", True),
    ("green_gram", "Green gram", "Ndengu", True),
    ("cowpea", "Cowpea", "Kunde", True),
    ("watermelon", "Watermelon", "Tikiti maji", False),
]
FARMER_NAMES = [
    "Joseph Kioko", "Mary Mutua", "Peter Mwangi", "Grace Wanjiku", "David Kavyu",
    "Anne Nzuki", "Samuel Kilonzo", "Ruth Muthoni", "Daniel Musyoka", "Jane Kariuki",
    "Elijah Mwendwa", "Faith Wambui", "John Mwila", "Catherine Njeri", "Michael Kibet",
    "Rose Mwikali", "Paul Kiptoo", "Sarah Wairimu", "Thomas Muindi", "Dorothy Ndunge",
    "Ezekiel Kipchoge", "Hannah Waceke", "Isaac Muriuki", "Joyce Mueni", "Kevin Otieno",
    "Lydia Wanjala", "Moses Kiprop", "Naomi Wanjiru", "Olivia Muthoni", "Patrick Kipkoech",
]


class Command(BaseCommand):
    help = "Seed wards across south-eastern and metropolitan Kenya for the demo."

    def handle(self, *args, **options):
        now = timezone.now()
        coop, _ = Tenant.objects.get_or_create(
            name="Kitui Farmers Cooperative", defaults={"type": Tenant.Types.COOPERATIVE}
        )
        sacco, _ = Tenant.objects.get_or_create(
            name="Kitui SACCO", defaults={"type": Tenant.Types.SACCO}
        )
        buyer, _ = Tenant.objects.get_or_create(
            name="Nairobi Grain Buyers", defaults={"type": Tenant.Types.BUYER}
        )
        self.stdout.write(f"Tenants: {Tenant.objects.count()}")

        wards = {}
        for name, county, region, lat, lng in WARDS:
            ward, _ = Ward.objects.get_or_create(
                name=name,
                county=county,
                defaults={"region": region, "lat": Decimal(lat), "lng": Decimal(lng)},
            )
            wards[name] = ward

        crops = {}
        for code, name_en, name_sw, storable in CROPS:
            crop, _ = Crop.objects.get_or_create(
                code=code,
                defaults={"name_en": name_en, "name_sw": name_sw, "storable": storable},
            )
            crops[code] = crop

        users = {}
        user_specs = [
            ("+254700000001", "Amina Mwende", User.Roles.AGENT, coop, False),
            ("+254700000002", "John Kioko", User.Roles.AGENT, coop, False),
            ("+254700000003", "Cooperative Admin", User.Roles.COOP_ADMIN, coop, False),
            ("+254700000004", "Platform Admin", User.Roles.ADMIN, None, True),
            ("+254700000005", FARMER_NAMES[0], User.Roles.FARMER, coop, False),
        ]
        for phone, name, role, tenant, is_admin in user_specs:
            if is_admin:
                user, created = User.objects.get_or_create(
                    phone=phone,
                    defaults={
                        "name": name, "role": role, "tenant": tenant,
                        "is_staff": True, "is_superuser": True,
                    },
                )
            else:
                user, created = User.objects.get_or_create(
                    phone=phone,
                    defaults={"name": name, "role": role, "tenant": tenant},
                )
            user.set_password(PASSWORD)
            user.save()
            users[phone] = user

        farmers = []
        for index, name in enumerate(FARMER_NAMES):
            phone = f"+254710{index + 1:06d}"
            ward = WARDS[index % len(WARDS)][0]
            farmer, created = Farmer.objects.get_or_create(
                phone=phone,
                defaults={
                    "name": name,
                    "ward": wards[ward],
                    "tenant": coop,
                    "consent_given": True,
                    "consent_at": now,
                    "user": users["+254700000005"] if index == 0 else None,
                },
            )
            farmers.append(farmer)
            Plot.objects.get_or_create(
                farmer=farmer,
                ward=farmer.ward,
                acres=Decimal(str(round(1 + (index % 5) * 0.75, 2))),
            )

        ruleset, created = AdviceRuleSet.objects.get_or_create(
            version="v3",
            defaults={"config": load_file_config(), "active": True},
        )
        if not ruleset.active:
            ruleset.active = True
            ruleset.save(update_fields=["active"])

        demand_values = {
            "maize": Decimal("120"),
            "green_gram": Decimal("8") if "Kitui Central" else Decimal("60"),
            "cowpea": Decimal("60"),
            "watermelon": Decimal("40"),
        }
        for ward in wards.values():
            for code, crop in crops.items():
                expected = demand_values[code]
                if ward.name != "Kitui Central" and code == "green_gram":
                    expected = Decimal("60")
                DemandEstimate.objects.get_or_create(
                    ward=ward,
                    crop=crop,
                    season=SEASON,
                    defaults={"expected_demand_acres": expected},
                )
                first_start = date(2026, 11, 25) + timedelta(days=list(wards).index(ward.name) * 2)
                Slot.objects.get_or_create(
                    ward=ward,
                    crop=crop,
                    season=SEASON,
                    window_start=first_start,
                    defaults={
                        "window_end": first_start + timedelta(days=10),
                        "capacity_acres": Decimal("60"),
                    },
                )
                second_start = date(2026, 12, 10) + timedelta(days=list(wards).index(ward.name) * 2)
                Slot.objects.get_or_create(
                    ward=ward,
                    crop=crop,
                    season=SEASON,
                    window_start=second_start,
                    defaults={
                        "window_end": second_start + timedelta(days=10),
                        "capacity_acres": Decimal("80"),
                    },
                )

        from planting.models import PlantingIntent

        if PlantingIntent.objects.count() == 0:
            agent = users["+254700000001"]
            for ward_name, ward in wards.items():
                ward_farmers = [f for f in farmers if f.ward_id == ward.id][:5]
                for index, farmer in enumerate(ward_farmers):
                    plot = farmer.plots.first()
                    for code in ("maize", "green_gram", "cowpea"):
                        planting_services.register_intent(
                            agent,
                            {
                                "farmer": farmer,
                                "plot": plot,
                                "crop": crops[code],
                                "acres": Decimal(str(1.5 + (index % 3) * 0.75)),
                                "season": SEASON,
                            },
                        )
                    if index < 2:  # watermelon suppressed by the 5-farmer privacy rule
                        planting_services.register_intent(
                            agent,
                            {
                                "farmer": farmer,
                                "plot": plot,
                                "crop": crops["watermelon"],
                                "acres": Decimal("1.0"),
                                "season": SEASON,
                            },
                        )

        from records.models import Lot

        if Lot.objects.count() == 0:
            agent = users["+254700000001"]
            crop_cycle = [crops["green_gram"]] * 6 + [crops["maize"]] * 5 + [crops["cowpea"]] * 4
            for index in range(15):
                lot, token = records_services.register_lot(
                    agent,
                    {
                        "farmer": farmers[index],
                        "crop": crop_cycle[index],
                        "weight_kg": Decimal(str(400 + index * 10)),
                        "bag_count": 4 + index % 4,
                        "storage_method": "hermetic_bag",
                        "location_label": f"{farmers[index].ward.name} store {1 + index % 3}",
                        "moisture_pct": Decimal(str(round(12 + (index % 5) * 0.4, 1))),
                    },
                )
                records_services.add_event(
                    agent,
                    lot,
                    "MOISTURE_READING",
                    {"moisture_pct": round(13 + (index % 3) * 0.5, 1)},
                )
                records_services.add_event(
                    agent,
                    lot,
                    "WEIGHT_READING",
                    {"weight_kg": float(lot.initial_weight_kg) - (index % 4) * 2},
                )
                records_services.add_event(
                    agent,
                    lot,
                    "CHECKUP",
                    {"pest_signs": index % 5 == 0, "notes": "Routine check-up"},
                )
                if index == 0:
                    records_services.add_event(
                        agent, lot, "LOSS_RECORDED", {"loss_kg": 8, "cause": "Bruchid weevils"}
                    )
                if index == 3:
                    records_services.respond_to_verification(
                        token.token, "dispute", "Recorded weight is higher than what I stored."
                    )
                elif index in (5, 6, 7, 8):
                    records_services.respond_to_verification(token.token, "confirm")

        self._load_rainfall(wards)
        self._load_prices(wards, crops)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {Ward.objects.count()} wards, {Farmer.objects.count()} farmers, "
                f"{Lot.objects.count()} lots, {PlantingIntent.objects.count()} intents."
            )
        )
        self.stdout.write("Demo logins (password demo1234): agent@demo phone +254700000001, "
                          "coop@demo +254700000003, farmer@demo +254700000005")

    def _load_rainfall(self, wards):
        with (DATA_DIR / "chirps_rainfall.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                RainfallObservation.objects.get_or_create(
                    ward=wards[row["ward_name"]],
                    date=date.fromisoformat(row["date"]),
                    source=row["source"],
                    defaults={"rainfall_mm": Decimal(row["rainfall_mm"])},
                )

    def _load_prices(self, wards, crops):
        with (DATA_DIR / "prices.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                MarketPrice.objects.get_or_create(
                    ward=wards[row["ward_name"]],
                    crop=crops[row["crop"]],
                    date=date.fromisoformat(row["date"]),
                    defaults={
                        "price_per_kg_kes": Decimal(row["price_per_kg_kes"]),
                        "source": row["source"],
                    },
                )
