from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from core.models import Crop, Farmer, Tenant, User, Ward
from core.errors import ConflictError
from records import services
from records.models import AppendOnlyError, LotEvent


class RecordsFixture(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Demo Coop")
        self.ward = Ward.objects.create(name="Kitui Central", county="Kitui")
        self.crop = Crop.objects.create(
            code="green_gram", name_en="Green gram", name_sw="Ndengu"
        )
        self.agent = User.objects.create_user(
            phone="+254700000001", password="demo1234", name="Agent",
            role=User.Roles.AGENT, tenant=self.tenant,
        )
        self.farmer = Farmer.objects.create(
            name="Joseph Kioko", phone="+254710000001", ward=self.ward,
            tenant=self.tenant, consent_given=True,
        )

    def register_lot(self, weight=500):
        lot, token = services.register_lot(
            self.agent,
            {
                "farmer": self.farmer,
                "crop": self.crop,
                "weight_kg": Decimal(str(weight)),
                "bag_count": 5,
                "storage_method": "hermetic_bag",
                "location_label": "Kitui Central store 2",
                "moisture_pct": Decimal("12.5"),
            },
        )
        return lot, token


class RecordsServiceTests(RecordsFixture):
    def test_loss_calculation_uses_latest_weight_reading(self):
        lot, _ = self.register_lot()
        services.add_event(self.agent, lot, "WEIGHT_READING", {"weight_kg": 492})
        summary = services.get_summary(lot)
        self.assertEqual(summary["latest_weight_kg"], 492)
        self.assertEqual(summary["loss_kg"], 8)
        self.assertEqual(summary["loss_pct"], 1.6)
        self.assertEqual(summary["latest_moisture_pct"], 12.5)

    def test_v10_wet_initial_reading_schedules_retest_and_dry_reading_schedules_checks(self):
        lot, _ = self.register_lot(weight=500)
        maize = lot.crop
        maize.code = "maize"
        maize.save(update_fields=["code"])
        services.process_moisture_reading(lot, 14.0)
        lot.refresh_from_db()
        self.assertEqual(lot.moisture_status, "retest")
        self.assertTrue(lot.scheduled_checks.filter(kind="retest").exists())

        services.add_event(self.agent, lot, "MOISTURE_READING", {"moisture_pct": 12.5})
        lot.refresh_from_db()
        self.assertEqual(lot.moisture_status, "dry")
        self.assertEqual(lot.scheduled_checks.filter(kind="checkup").count(), 3)

    def test_v10_dry_matter_summary_is_reported_separately(self):
        lot, _ = self.register_lot(weight=500)
        services.add_event(self.agent, lot, "MOISTURE_READING", {"moisture_pct": 12.5})
        summary = services.get_summary(lot)
        self.assertIn("dry_matter_loss_kg", summary)
        self.assertIn("dry_matter_loss_pct", summary)

    def test_events_are_append_only(self):
        lot, _ = self.register_lot()
        event = lot.events.first()
        with self.assertRaises(AppendOnlyError):
            event.save()
        with self.assertRaises(AppendOnlyError):
            event.delete()

    def test_hash_chain_detects_tampering(self):
        lot, _ = self.register_lot()
        self.assertTrue(services.verify_chain(lot))
        event = lot.events.filter(type="MOISTURE_READING").first()
        LotEvent.objects.filter(pk=event.pk).update(payload={"moisture_pct": 99})
        self.assertFalse(services.verify_chain(lot))

    def test_moisture_payload_is_validated(self):
        with self.assertRaises(ValidationError):
            services.validate_event_payload("MOISTURE_READING", {"moisture_pct": 101})

    def test_verify_token_expiry_and_single_use(self):
        lot, token = self.register_lot()
        token.expires_at = timezone.now() - timedelta(days=1)
        token.save(update_fields=["expires_at"])
        with self.assertRaises(ConflictError):
            services.get_verification_data(token.token)

        token.expires_at = timezone.now() + timedelta(days=14)
        token.save(update_fields=["expires_at"])
        data = services.get_verification_data(token.token)
        self.assertFalse(data["already_responded"])
        services.respond_to_verification(token.token, "confirm")
        with self.assertRaises(ConflictError):
            services.respond_to_verification(token.token, "confirm")
        self.assertTrue(lot.events.filter(type="VERIFIED").exists())

    def test_lot_registration_api_accepts_farmer_id(self):
        token, _ = Token.objects.get_or_create(user=self.agent)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        response = client.post(
            reverse("lot-list"),
            {
                "farmer_id": str(self.farmer.id),
                "crop": self.crop.code,
                "weight_kg": "500.00",
                "bag_count": 5,
                "storage_method": "hermetic_bag",
                "location_label": "Kitui Central store 2",
                "moisture_pct": "12.5",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["crop"], "green_gram")
        self.assertIn("verification_url", response.data)

    def test_dispute_changes_lot_status(self):
        lot, token = self.register_lot()
        services.respond_to_verification(token.token, "dispute", "Weight looks wrong")
        lot.refresh_from_db()
        self.assertEqual(lot.status, "disputed")
        self.assertTrue(lot.events.filter(type="DISPUTED").exists())


class CorrectionAndLinkTests(RecordsFixture):
    """Corrections feed the loss figure; verify links point at verify.html."""

    def test_correction_replaces_weight_in_loss_without_editing_history(self):
        lot, _ = self.register_lot()
        wrong = services.add_event(self.agent, lot, "WEIGHT_READING", {"weight_kg": 49.2})
        services.add_event(
            self.agent, lot, "CORRECTION",
            {"corrects_event_id": str(wrong.id), "new_payload": {"weight_kg": 492},
             "reason": "Typed 49.2 instead of 492"},
        )
        summary = services.get_summary(lot)
        self.assertEqual(summary["latest_weight_kg"], 492)
        self.assertEqual(summary["loss_kg"], 8)
        wrong.refresh_from_db()
        self.assertEqual(wrong.payload["weight_kg"], 49.2)
        self.assertTrue(services.verify_chain(lot))

    def test_correction_with_bad_weight_is_rejected(self):
        lot, _ = self.register_lot()
        reading = services.add_event(self.agent, lot, "WEIGHT_READING", {"weight_kg": 490})
        with self.assertRaises(ValidationError):
            services.add_event(
                self.agent, lot, "CORRECTION",
                {"corrects_event_id": str(reading.id), "new_payload": {"weight_kg": "abc"},
                 "reason": "test"},
            )

    def test_verification_url_uses_html_verify_page(self):
        from django.test import override_settings

        _lot, token = self.register_lot()
        # Pin the setting: backend/.env may point it at the React app instead.
        with override_settings(FRONTEND_VERIFY_PATH="/verify.html?token="):
            self.assertTrue(
                services.verification_url(token).endswith(f"/verify.html?token={token.token}")
            )

    def test_public_verify_ignores_a_stale_token(self):
        _lot, token = self.register_lot()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
        response = client.get(f"/api/v1/verify/{token.token}/")
        self.assertEqual(response.status_code, 200, response.content)


class FarmerLotViewTests(RecordsFixture):
    def test_farmer_can_list_only_own_lots(self):
        lot, _ = self.register_lot()
        farmer_user = User.objects.create_user(
            phone="+254799000020", password="demo1234", name="Linked Farmer",
            role=User.Roles.FARMER, tenant=self.tenant,
        )
        self.farmer.user = farmer_user
        self.farmer.save(update_fields=["user"])
        token, _ = Token.objects.get_or_create(user=farmer_user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        response = client.get(reverse("lot-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(str(response.data["results"][0]["id"]), str(lot.id))


class SafeguardRegressionTests(RecordsFixture):
    """Bugs found in the review of 18 Nov 2026."""

    def agent_client(self):
        token, _ = Token.objects.get_or_create(user=self.agent)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        return client

    def test_agent_cannot_forge_farmer_confirmation_through_events_api(self):
        lot, _ = self.register_lot()
        client = self.agent_client()
        for event_type, payload in (
            ("VERIFIED", {"method": "link"}),
            ("DISPUTED", {"reason": "x"}),
            ("REGISTERED", {"weight_kg": 1, "bag_count": 1, "storage_method": "x"}),
        ):
            response = client.post(
                f"/api/v1/lots/{lot.id}/events/", {"type": event_type, "payload": payload}
            )
            self.assertEqual(response.status_code, 400, (event_type, response.content))
        self.assertFalse(lot.events.filter(type__in=["VERIFIED", "DISPUTED"]).exists())

    def test_agent_can_still_add_readings_through_events_api(self):
        lot, _ = self.register_lot()
        response = self.agent_client().post(
            f"/api/v1/lots/{lot.id}/events/",
            {"type": "WEIGHT_READING", "payload": {"weight_kg": 495}},
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_bad_correction_target_is_a_400_not_a_500(self):
        lot, _ = self.register_lot()
        response = self.agent_client().post(
            f"/api/v1/lots/{lot.id}/events/",
            {"type": "CORRECTION", "payload": {
                "corrects_event_id": "not-a-uuid", "new_payload": {"weight_kg": 1}, "reason": "x"}},
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_nan_and_infinity_are_not_valid_readings(self):
        for bad in ("nan", "inf", float("inf")):
            with self.assertRaises(ValidationError):
                services.validate_event_payload("WEIGHT_READING", {"weight_kg": bad})

    def test_non_storable_crop_cannot_be_registered_as_a_lot(self):
        melon = Crop.objects.create(
            code="watermelon", name_en="Watermelon", name_sw="Tikiti maji", storable=False
        )
        response = self.agent_client().post(
            reverse("lot-list"),
            {"farmer_id": str(self.farmer.id), "crop": melon.code, "weight_kg": "100",
             "bag_count": 1, "storage_method": "other", "location_label": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)

    def test_user_without_a_cooperative_sees_no_lots(self):
        self.register_lot()
        loner = User.objects.create_user(
            phone="+254700000099", password="demo1234", name="No coop", role=User.Roles.AGENT
        )
        self.assertEqual(services.lots_for_user(loner).count(), 0)

    def test_farmer_links_are_found_even_if_login_phone_differs(self):
        _lot, token = self.register_lot()
        login = User.objects.create_user(
            phone="+254700000055", password="demo1234", name="Joseph", role=User.Roles.FARMER,
            tenant=self.tenant,
        )
        self.farmer.user = login
        self.farmer.save()
        token_auth, _ = Token.objects.get_or_create(user=login)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token_auth.key)
        response = client.get("/api/v1/me/verification-links/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()["links"]), 1)
