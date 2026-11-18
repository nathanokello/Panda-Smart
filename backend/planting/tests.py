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


class PlantingFixture(TestCase):
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


class PlantingTests(PlantingFixture):
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


class HtmlFrontendPlantingTests(PlantingFixture):
    """Added with the HTML frontend integration."""

    def test_oversubscription_pct_is_share_above_demand(self):
        # 6 farmers x 2 acres = 12 planned against 8 expected -> 50% above demand.
        for farmer in self.farmers:
            services.register_intent(
                self.agent, {"farmer": farmer, "crop": self.green_gram, "acres": Decimal("2")}
            )
        dashboard = services.get_ward_dashboard(self.ward.id)
        row = next(item for item in dashboard["crops"] if item["crop"] == "green_gram")
        self.assertFalse(row["suppressed"])
        self.assertEqual(row["oversubscription_pct"], 50.0)

    def test_farmer_can_list_only_own_intents(self):
        farmer_user = User.objects.create_user(
            phone="+254799000001", password="demo1234", name="Farmer login",
            role=User.Roles.FARMER, tenant=self.tenant,
        )
        own = self.farmers[0]
        own.user = farmer_user
        own.save(update_fields=["user"])
        services.register_intent(self.agent, {"farmer": own, "crop": self.cowpea, "acres": Decimal("1")})
        services.register_intent(
            self.agent, {"farmer": self.farmers[1], "crop": self.cowpea, "acres": Decimal("1")}
        )
        token, _ = Token.objects.get_or_create(user=farmer_user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        response = client.get(reverse("planting-intent-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["farmer_id"], str(own.id))

    def test_ussd_replies_fit_one_screen(self):
        phone = "+254710000001"
        reply = handle_ussd("session-2", phone, "1*1*1")
        self.assertLessEqual(len(reply), 182)

    def test_ussd_accepts_local_phone_format(self):
        services.register_intent(
            self.agent, {"farmer": self.farmers[0], "crop": self.cowpea, "acres": Decimal("1")}
        )
        reply = handle_ussd("session-3", "0710000001", "2")
        self.assertIn("Cowpea", reply)

    def test_ussd_callback_needs_secret_when_configured(self):
        from django.test import override_settings

        client = APIClient()
        form = {"sessionId": "s-9", "phoneNumber": "+254710000001", "text": ""}
        with override_settings(USSD_CALLBACK_SECRET="s3cret"):
            self.assertEqual(client.post("/api/v1/ussd/", form, format="multipart").status_code, 403)
            ok = client.post("/api/v1/ussd/?key=s3cret", form, format="multipart")
            self.assertEqual(ok.status_code, 200)
            self.assertTrue(ok.content.decode().startswith("CON "))
        with override_settings(USSD_CALLBACK_SECRET="", DEBUG=False):
            self.assertEqual(client.post("/api/v1/ussd/", form, format="multipart").status_code, 503)


class WeatherTests(PlantingFixture):
    """Weather parsing and storage. Network calls are replaced with fixed data."""

    NASA = {"properties": {"parameter": {"PRECTOTCORR": {
        "20261101": 0.0, "20261102": 12.5, "20261103": -999.0, "20261104": 9.1}}}}
    METEO = {"daily": {"time": ["2026-11-18", "2026-11-19"], "precipitation_sum": [3.2, 0.0],
                       "temperature_2m_max": [29.1, 30.4], "temperature_2m_min": [17.0, 17.8],
                       "precipitation_probability_max": [70, 10]}}

    def test_nasa_parser_skips_missing_days(self):
        from planting.weather import parse_nasa_power_rainfall

        rows = parse_nasa_power_rainfall(self.NASA)
        self.assertEqual([d.isoformat() for d, _ in rows], ["2026-11-01", "2026-11-02", "2026-11-04"])
        self.assertEqual(rows[1][1], 12.5)

    def test_open_meteo_parser(self):
        from planting.weather import parse_open_meteo_daily

        days = parse_open_meteo_daily(self.METEO)
        self.assertEqual(days[0], {"date": "2026-11-18", "rain_mm": 3.2, "temp_max_c": 29.1,
                                   "temp_min_c": 17.0, "rain_chance_pct": 70})

    def test_fetch_rainfall_command_stores_and_updates(self):
        from io import StringIO
        from unittest import mock

        from django.core.management import call_command
        from planting.weather import parse_nasa_power_rainfall

        self.ward.lat, self.ward.lng = Decimal("-1.3678"), Decimal("38.0103")
        self.ward.save()
        with mock.patch("planting.management.commands.fetch_rainfall.fetch_nasa_power_rainfall",
                        return_value=parse_nasa_power_rainfall(self.NASA)):
            call_command("fetch_rainfall", "--days", "30", stdout=StringIO())
            call_command("fetch_rainfall", "--days", "30", stdout=StringIO())
        rows = services.RainfallObservation.objects.filter(ward=self.ward, source="NASA_POWER")
        self.assertEqual(rows.count(), 3)

    def test_advice_uses_one_rainfall_source(self):
        today = timezone.localdate()
        for source in ("CHIRPS", "NASA_POWER"):
            services.RainfallObservation.objects.create(
                ward=self.ward, date=today - timedelta(days=3), rainfall_mm=Decimal("12"), source=source)
        # 12 mm from one source is below the 20 mm onset; counted twice it would pass.
        advice = services.get_advice(self.ward, self.green_gram)
        self.assertIn("No rainfall onset", advice["rationale"])

    def test_weather_endpoint_off_by_default_and_cached_when_on(self):
        from unittest import mock

        from django.core.cache import cache
        from django.test import override_settings
        from planting.weather import parse_open_meteo_daily

        cache.clear()
        token, _ = Token.objects.get_or_create(user=self.agent)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        url = f"/api/v1/wards/{self.ward.id}/weather/"
        with override_settings(OPEN_METEO_ENABLED=False):
            self.assertEqual(client.get(url).json(), {"enabled": False})
        self.ward.lat, self.ward.lng = Decimal("-1.3678"), Decimal("38.0103")
        self.ward.save()
        with override_settings(OPEN_METEO_ENABLED=True), mock.patch(
            "planting.weather.fetch_open_meteo_forecast",
            return_value=parse_open_meteo_daily(self.METEO),
        ) as fetch:
            first = client.get(url).json()
            client.get(url)
        self.assertEqual(first["days"][0]["rain_mm"], 3.2)
        self.assertEqual(fetch.call_count, 1)  # second call served from cache


class SeasonHistoryTests(PlantingFixture):
    """Season records, soil tests and the 'what worked before' summary."""

    def setUp(self):
        super().setUp()
        self.maize = Crop.objects.create(code="maize", name_en="Maize", name_sw="Mahindi")
        self.farmer_user = User.objects.create_user(
            phone="+254799000002", password="demo1234", name="Farmer One",
            role=User.Roles.FARMER, tenant=self.tenant)
        self.farmer = self.farmers[0]
        self.farmer.user = self.farmer_user
        self.farmer.save(update_fields=["user"])

    def client_for(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        return client

    def add_season(self, client, **extra):
        payload = {"season": "2025-long-rains", "crop": "maize", "acres": "2", "harvest_kg": "1800"}
        payload.update(extra)
        return client.post(f"/api/v1/farmers/{self.farmer.id}/seasons/", payload, format="json")

    def test_farmer_records_seasons_and_sees_best_one(self):
        client = self.client_for(self.farmer_user)
        self.assertEqual(self.add_season(client, variety="H513", methods="DAP at planting").status_code, 201)
        response = self.add_season(client, season="2025-short-rains", harvest_kg="1000", variety="Local")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["yield_kg_per_acre"], 500.0)
        history = client.get(f"/api/v1/farmers/{self.farmer.id}/history/").data
        maize = next(row for row in history["crops"] if row["crop"] == "maize")
        self.assertEqual(maize["seasons"], 2)
        self.assertEqual(maize["avg_yield_kg_per_acre"], 700.0)
        self.assertEqual(maize["best"]["variety"], "H513")
        self.assertEqual(maize["best"]["yield_kg_per_acre"], 900.0)

    def test_harvest_added_later_and_dates_checked(self):
        client = self.client_for(self.farmer_user)
        record = self.add_season(client, harvest_kg=None, planted_on="2026-03-20").data
        bad = client.patch(f"/api/v1/seasons/{record['id']}/", {"harvested_on": "2026-02-01"}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = client.patch(f"/api/v1/seasons/{record['id']}/",
                          {"harvested_on": "2026-08-01", "harvest_kg": "1500"}, format="json")
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.data["yield_kg_per_acre"], 750.0)

    def test_other_farmers_cannot_see_or_add_records(self):
        stranger = User.objects.create_user(
            phone="+254799000003", password="demo1234", name="Stranger",
            role=User.Roles.FARMER, tenant=self.tenant)
        client = self.client_for(stranger)
        self.assertEqual(client.get(f"/api/v1/farmers/{self.farmer.id}/seasons/").status_code, 404)
        self.assertEqual(self.add_season(client).status_code, 404)

    def test_agent_in_same_cooperative_can_record(self):
        self.assertEqual(self.add_season(self.client_for(self.agent)).status_code, 201)

    def test_soil_test_gives_guidance_and_needs_a_value(self):
        client = self.client_for(self.farmer_user)
        url = f"/api/v1/farmers/{self.farmer.id}/soil-tests/"
        empty = client.post(url, {"tested_on": "2026-10-01", "source": "kit"}, format="json")
        self.assertEqual(empty.status_code, 400)
        response = client.post(url, {"tested_on": "2026-10-01", "source": "lab", "ph": "5.1",
                                     "organic_carbon_pct": "0.8"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        text = " ".join(response.data["guidance"])
        self.assertIn("acidic", text)
        self.assertIn("Organic matter is low", text)
        self.assertIn("extension officer", text)
        history = client.get(f"/api/v1/farmers/{self.farmer.id}/history/").data
        self.assertEqual(history["latest_soil_test"]["tested_on"], "2026-10-01")

    def test_history_includes_storage_loss(self):
        from records import services as records_services

        lot, _ = records_services.register_lot(self.agent, {
            "farmer": self.farmer, "crop": self.maize, "weight_kg": Decimal("1000"), "bag_count": 10,
            "storage_method": "polypropylene_bag", "location_label": "Home store"})
        records_services.add_event(self.agent, lot, "WEIGHT_READING", {"weight_kg": 900})
        history = self.client_for(self.farmer_user).get(f"/api/v1/farmers/{self.farmer.id}/history/").data
        maize = next(row for row in history["crops"] if row["crop"] == "maize")
        self.assertEqual(maize["storage_lots"], 1)
        self.assertEqual(maize["avg_storage_loss_pct"], 10.0)


class MarketplaceTests(PlantingFixture):
    def setUp(self):
        super().setUp()
        self.farmer_user = User.objects.create_user(
            phone="+254799000010", password="demo1234", name="Market Farmer",
            role=User.Roles.FARMER, tenant=self.tenant)
        self.farmer = self.farmers[0]
        self.farmer.user = self.farmer_user
        self.farmer.save(update_fields=["user"])

    def client_for(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        return client

    def test_farmer_lists_and_updates_produce(self):
        client = self.client_for(self.farmer_user)
        response = client.post("/api/v1/marketplace/", {
            "crop": "green_gram",
            "quantity_kg": "500",
            "price_per_kg_kes": "95",
            "description": "Clean grain",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        listing_id = response.data["id"]
        public = APIClient().get("/api/v1/marketplace/")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(len(public.data), 1)
        updated = client.patch(f"/api/v1/marketplace/{listing_id}/", {"status": "sold"}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["status"], "sold")

    def test_public_marketplace_does_not_require_login(self):
        response = APIClient().get("/api/v1/marketplace/")
        self.assertEqual(response.status_code, 200)


class ReviewRegressionTests(PlantingFixture):
    """Bugs found in the review of 18 Nov 2026."""

    def test_advice_window_never_starts_in_the_past(self):
        # setUp loads rainfall for the last 11 days, so the onset is already behind us.
        for obs in services.RainfallObservation.objects.filter(ward=self.ward):
            obs.rainfall_mm = Decimal("10")
            obs.save()
        advice = services.get_advice(self.ward, self.green_gram)
        self.assertGreaterEqual(advice["recommended_window"]["start"], date.today().isoformat())

    def test_plot_must_belong_to_the_farmer(self):
        from core.models import Plot

        other_plot = Plot.objects.create(
            farmer=self.farmers[1], ward=self.ward, acres=Decimal("2")
        )
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            services.register_intent(
                self.agent,
                {"farmer": self.farmers[0], "plot": other_plot, "crop": self.green_gram,
                 "acres": Decimal("1")},
            )

    def test_staff_without_a_cooperative_see_no_farmers_or_intents(self):
        from core import services as core_services

        loner = User.objects.create_user(
            phone="+254700000098", password="demo1234", name="No coop", role=User.Roles.AGENT
        )
        self.assertEqual(core_services.farmers_for_user(loner).count(), 0)
        self.assertEqual(services.intents_for_user(loner).count(), 0)
