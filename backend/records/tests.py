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


class RecordsServiceTests(TestCase):
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

    def test_loss_calculation_uses_latest_weight_reading(self):
        lot, _ = self.register_lot()
        services.add_event(self.agent, lot, "WEIGHT_READING", {"weight_kg": 492})
        summary = services.get_summary(lot)
        self.assertEqual(summary["latest_weight_kg"], 492)
        self.assertEqual(summary["loss_kg"], 8)
        self.assertEqual(summary["loss_pct"], 1.6)
        self.assertEqual(summary["latest_moisture_pct"], 12.5)

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
