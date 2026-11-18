from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from core.models import Farmer, Ward, Plot
from .models import FarmProfile, EnvironmentalObservation, CropRequirement, RegionalPlantingIntent
from django.utils import timezone

User = get_user_model()

class GeoAgriApiTests(TestCase):
    def setUp(self):
        self.ward = Ward.objects.create(name="Kibwezi East", county="Makueni")
        self.user = User.objects.create_user(phone="0712345678", password="test-pass-123", name="Pilot Farmer")
        self.farmer = Farmer.objects.create(user=self.user, name="Pilot Farmer", phone="0712345678", ward=self.ward, consent_given=True)
        self.plot = Plot.objects.create(farmer=self.farmer, ward=self.ward, acres=2, lat=-2.2, lng=37.9)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_farm_list_does_not_expose_plot_without_geoagri_profile(self):
        response = self.client.get("/api/v1/geoagri/farms/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_environment_requires_explicit_location_consent(self):
        profile = FarmProfile.objects.create(plot=self.plot, location_consent=False)
        response = self.client.get(f"/api/v1/geoagri/farms/{self.plot.id}/environment/")
        self.assertEqual(response.status_code, 403)

    def test_no_crop_requirement_means_insufficient_data_not_fake_score(self):
        profile = FarmProfile.objects.create(plot=self.plot, location_consent=True)
        response = self.client.get(f"/api/v1/geoagri/farms/{self.plot.id}/suitability/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_regional_intent_requires_user_owned_plot(self):
        response = self.client.post("/api/v1/geoagri/planting-intents/", {"plot": "00000000-0000-0000-0000-000000000000", "crop_code": "maize", "share_for_aggregation": True})
        self.assertEqual(response.status_code, 400)
