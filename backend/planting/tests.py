from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import Crop, Farmer, Tenant, User, Ward
from planting import services
from planting.ussd import handle_ussd


class PlantingTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo Coop")
        self.ward = Ward.objects.create(
            name="Kitui Central", county="Kitui", region=Ward.Regions.SOUTH_EASTERN
        )
        self.green_gram = Crop.objects.create(
            code="green_gram", name_en="Green gram", name_sw="Ndengu"
        )
        self.cowpea = Crop.objects.create(code="cowpea", name_en="Cowpea", name_sw="Kunde")
        self.agent = User.objects.create_user(
            phone="+254700000001", password="demo1234", name="Agent",
            role=User.Roles.AGENT, tenant=self.tenant,
        )
        self.farmers = [
            Farmer.objects.create(
                name=f"Farmer {index}", phone=f"+25471000{index:04d}", ward=self.ward,
                tenant=self.tenant, consent_given=True,
            )
            for index in range(1, 7)
        ]
        for crop, demand in ((self.green_gram, Decimal("8")), (self.cowpea, Decimal("60"))):
            services.DemandEstimate.objects.create(
                ward=self.ward, crop=crop, season=services.DEFAULT_SEASON,
                expected_demand_acres=demand,
            )
            services.Slot.objects.create(
                ward=self.ward, crop=crop, season=services.DEFAULT_SEASON,
                window_start=date(2026, 11, 25), window_end=date(2026, 12, 5),
                capacity_acres=Decimal("100"),
            )
            services.Slot.objects.create(
                ward=self.ward, crop=crop, season=services.DEFAULT_SEASON,
                window_start=date(2026, 12, 10), window_end=date(2026, 12, 20),
                capacity_acres=Decimal("80"),
            )

    def test_advice_shape(self):
        for day in range(1, 12):
            services.RainfallObservation.objects.create(
                ward=self.ward,
                date=timezone.localdate() - timedelta(days=12 - day),
                rainfall_mm=Decimal("3"),
            )
        advice = services.get_advice(self.ward, self.green_gram)
        self.assertEqual(advice["crop"], "green_gram")
        self.assertIn("start", advice["recommended_window"])
        self.assertIn("end", advice["recommended_window"])
        self.assertIsInstance(advice["confidence"], float)
        self.assertEqual(advice["rule_set_version"], "v3")

    def test_oversubscription_moves_intent_to_later_slot(self):
        intent = services.register_intent(
            self.agent,
            {
                "farmer": self.farmers[0], "crop": self.green_gram,
                "acres": Decimal("10"), "season": services.DEFAULT_SEASON,
            },
        )
        self.assertTrue(intent.oversubscribed)
        self.assertIn("later window", intent.warning)
        self.assertEqual(intent.slot.window_start, date(2026, 12, 10))
        self.assertIn("cowpea", [item["crop"] for item in intent.alternatives])

    def test_dashboard_suppresses_small_crops(self):
        for farmer in self.farmers[:5]:
            services.register_intent(
                self.agent,
                {
                    "farmer": farmer, "crop": self.green_gram,
                    "acres": Decimal("2"), "season": services.DEFAULT_SEASON,
                },
            )
        for farmer in self.farmers[:2]:
            services.register_intent(
                self.agent,
                {
                    "farmer": farmer, "crop": self.cowpea,
                    "acres": Decimal("2"), "season": services.DEFAULT_SEASON,
                },
            )
        dashboard = services.get_ward_dashboard(self.ward.id)
        by_crop = {item["crop"]: item for item in dashboard["crops"]}
        self.assertFalse(by_crop["green_gram"]["suppressed"])
        self.assertTrue(by_crop["cowpea"]["suppressed"])
        self.assertIsNone(by_crop["cowpea"]["intended_acres"])

    def test_sell_flag_holds_when_price_below_average(self):
        for farmer in self.farmers[:5]:
            services.register_intent(
                self.agent,
                {
                    "farmer": farmer, "crop": self.green_gram,
                    "acres": Decimal("1"), "season": services.DEFAULT_SEASON,
                },
            )
        for months_ago, price in ((3, 100), (2, 100), (1, 100), (0, 85)):
            services.MarketPrice.objects.create(
                ward=self.ward, crop=self.green_gram,
                date=timezone.localdate() - timedelta(days=30 * months_ago),
                price_per_kg_kes=Decimal(str(price)),
            )
        dashboard = services.get_ward_dashboard(self.ward.id)
        green_gram = next(item for item in dashboard["crops"] if item["crop"] == "green_gram")
        self.assertEqual(green_gram["sell_flag"], "hold")

    def test_dashboard_endpoints_for_coop_admin(self):
        coop_admin = User.objects.create_user(
            phone="+254700000003", password="demo1234", name="Coop Admin",
            role=User.Roles.COOP_ADMIN, tenant=self.tenant,
        )
        token, _ = Token.objects.get_or_create(user=coop_admin)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        self.assertEqual(client.get(reverse("dashboard-wards")).status_code, 200)
        self.assertEqual(
            client.get(reverse("dashboard-ward", args=[self.ward.id])).status_code, 200
        )

    def test_intent_registration_api_accepts_farmer_id(self):
        token, _ = Token.objects.get_or_create(user=self.agent)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        response = client.post(
            reverse("planting-intent-list"),
            {
                "farmer_id": str(self.farmers[0].id),
                "crop": self.green_gram.code,
                "acres": "2.00",
                "season": services.DEFAULT_SEASON,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["crop"], "green_gram")
        self.assertIn("slot", response.data)

    def test_ussd_menu_flow(self):
        phone = "+254710000001"
        self.assertTrue(handle_ussd("session-1", phone, "").startswith("CON "))
        self.assertIn("Select ward", handle_ussd("session-1", phone, "1"))
        self.assertIn("Select crop", handle_ussd("session-1", phone, "1*1"))
        self.assertTrue(handle_ussd("session-1", phone, "1*1*1").startswith("END "))
