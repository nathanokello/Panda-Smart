from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from core.models import Farmer, Tenant, User, Ward


class AuthAndTenantTests(APITestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(name="Coop A")
        self.tenant_b = Tenant.objects.create(name="Coop B")
        self.ward = Ward.objects.create(name="Kitui Central", county="Kitui")
        self.agent_a = User.objects.create_user(
            phone="+254700000001", password="demo1234", name="Agent A",
            role=User.Roles.AGENT, tenant=self.tenant_a,
        )
        self.agent_b = User.objects.create_user(
            phone="+254700000002", password="demo1234", name="Agent B",
            role=User.Roles.AGENT, tenant=self.tenant_b,
        )
        Farmer.objects.create(
            name="Farmer A", phone="+254710000001", ward=self.ward,
            tenant=self.tenant_a, consent_given=True,
        )
        Farmer.objects.create(
            name="Farmer B", phone="+254710000002", ward=self.ward,
            tenant=self.tenant_b, consent_given=True,
        )

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_health_endpoint_is_public(self):
        for url in ("/health", "/health/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})

    def test_login_returns_token_and_user_shape(self):
        response = self.client.post(
            reverse("auth-login"), {"phone": "+254700000001", "password": "demo1234"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["role"], "agent")
        self.assertEqual(str(response.data["user"]["tenant_id"]), str(self.tenant_a.id))

    def test_login_error_uses_error_envelope(self):
        response = self.client.post(
            reverse("auth-login"), {"phone": "+254700000001", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "unauthenticated")

    def test_farmer_list_is_tenant_isolated(self):
        self.authenticate(self.agent_a)
        response = self.client.get(reverse("farmer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Farmer A")

    def test_farmer_registration_requires_consent(self):
        self.authenticate(self.agent_a)
        response = self.client.post(
            reverse("farmer-list"),
            {
                "name": "No Consent", "phone": "+254710000099",
                "ward": str(self.ward.id), "consent_given": False,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("consent_given", response.data["error"]["fields"])

    def test_unauthenticated_request_uses_error_envelope(self):
        response = self.client.get(reverse("farmer-list"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "unauthenticated")
