from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
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


class HtmlFrontendIntegrationTests(APITestCase):
    """Behaviour the HTML frontend relies on (added with the frontend integration)."""

    def setUp(self):
        cache.clear()  # throttle counters live in the cache
        self.tenant = Tenant.objects.create(name="Coop A")
        self.ward = Ward.objects.create(name="Kitui Central", county="Kitui")

    def register(self, phone="0712 345 678", **extra):
        payload = {
            "name": "Mary Wanjiru",
            "phone": phone,
            "password": "Mavuno-2026!",
            "ward_id": str(self.ward.id),
            "consent_given": True,
        }
        payload.update(extra)
        return self.client.post("/api/v1/auth/register/farmer/", payload, format="json")

    def test_self_registration_creates_farmer_and_normalises_phone(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["user"]["role"], "farmer")
        self.assertEqual(response.data["user"]["phone"], "+254712345678")
        self.assertIsNotNone(response.data["user"]["farmer_id"])
        farmer = Farmer.objects.get(phone="+254712345678")
        self.assertTrue(farmer.consent_given)
        self.assertEqual(farmer.tenant, self.tenant)

    def test_self_registration_cannot_choose_role(self):
        response = self.register(role="admin")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get(phone="+254712345678").role, "farmer")

    def test_self_registration_requires_consent(self):
        response = self.register(consent_given=False)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(phone="+254712345678").exists())

    def test_duplicate_phone_in_another_format_is_rejected(self):
        self.assertEqual(self.register().status_code, 201)
        response = self.register(phone="+254712345678")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_login_accepts_local_phone_format(self):
        self.register()
        response = self.client.post(
            "/api/v1/auth/login/", {"phone": "0712345678", "password": "Mavuno-2026!"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_logout_revokes_token(self):
        token = self.register().data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(self.client.post("/api/v1/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    def test_wards_ignore_a_stale_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
        response = self.client.get("/api/v1/wards/")
        self.assertEqual(response.status_code, 200)

    def test_expired_token_is_rejected_and_login_issues_a_new_one(self):
        old = self.register().data["token"]
        Token.objects.filter(key=old).update(created=timezone.now() - timedelta(days=30))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {old}")
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)
        self.client.credentials()
        response = self.client.post(
            "/api/v1/auth/login/", {"phone": "0712345678", "password": "Mavuno-2026!"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data["token"], old)

    def test_login_is_limited_per_phone_number(self):
        from core.authentication import LoginPhoneThrottle

        self.register()
        rates = {"login": "100/min", "login_phone": "2/min"}
        with mock.patch.object(LoginPhoneThrottle, "THROTTLE_RATES", rates):
            for _ in range(2):
                self.client.post("/api/v1/auth/login/", {"phone": "0712345678", "password": "wrong"}, format="json")
            # Same number in another format still counts against the same limit.
            response = self.client.post(
                "/api/v1/auth/login/", {"phone": "+254 712 345 678", "password": "wrong"}, format="json"
            )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "rate_limited")


class StaffUserManagementTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.coop_a = Tenant.objects.create(name="Coop A")
        self.coop_b = Tenant.objects.create(name="Coop B")
        self.admin = User.objects.create_user(phone="+254700000100", password="demo1234", name="Admin", role="admin")
        self.coop_admin = User.objects.create_user(
            phone="+254700000101", password="demo1234", name="Coop Admin A", role="coop_admin", tenant=self.coop_a)
        self.agent_a = User.objects.create_user(
            phone="+254700000102", password="demo1234", name="Agent A", role="agent", tenant=self.coop_a)
        self.agent_b = User.objects.create_user(
            phone="+254700000103", password="demo1234", name="Agent B", role="agent", tenant=self.coop_b)

    def as_user(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def new_user(self, **extra):
        payload = {"name": "New Agent", "phone": "0722000111", "role": "agent", "password": "Hifadhi-2026!"}
        payload.update(extra)
        return self.client.post("/api/v1/users/", payload, format="json")

    def test_agents_and_farmers_cannot_manage_users(self):
        self.as_user(self.agent_a)
        self.assertEqual(self.client.get("/api/v1/users/").status_code, 403)
        self.assertEqual(self.new_user().status_code, 403)

    def test_coop_admin_sees_only_own_cooperative(self):
        self.as_user(self.coop_admin)
        response = self.client.get("/api/v1/users/")
        names = {row["name"] for row in response.data["results"]}
        self.assertIn("Agent A", names)
        self.assertNotIn("Agent B", names)
        self.assertNotIn("Admin", names)
        self.assertEqual(self.client.get(f"/api/v1/users/{self.agent_b.id}/").status_code, 404)

    def test_coop_admin_creates_agents_in_own_cooperative_only(self):
        self.as_user(self.coop_admin)
        response = self.new_user(tenant_id=str(self.coop_b.id))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["tenant_id"], str(self.coop_a.id))
        self.assertEqual(response.data["phone"], "+254722000111")
        self.assertEqual(self.new_user(phone="0722000112", role="admin").status_code, 400)
        self.assertEqual(self.new_user(phone="0722000113", role="coop_admin").status_code, 400)

    def test_weak_password_is_a_400_not_a_crash(self):
        self.as_user(self.admin)
        response = self.new_user(password="12345678", tenant_id=str(self.coop_a.id))
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["error"]["fields"])

    def test_deactivating_signs_the_user_out_and_blocks_login(self):
        Token.objects.get_or_create(user=self.agent_a)
        self.as_user(self.coop_admin)
        response = self.client.patch(f"/api/v1/users/{self.agent_a.id}/", {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Token.objects.filter(user=self.agent_a).exists())
        self.client.credentials()
        login = self.client.post("/api/v1/auth/login/", {"phone": "+254700000102", "password": "demo1234"}, format="json")
        self.assertEqual(login.status_code, 401)

    def test_nobody_changes_their_own_account_or_promotes_beyond_their_role(self):
        self.as_user(self.coop_admin)
        own = self.client.patch(f"/api/v1/users/{self.coop_admin.id}/", {"role": "admin"}, format="json")
        self.assertEqual(own.status_code, 403)
        promote = self.client.patch(f"/api/v1/users/{self.agent_a.id}/", {"role": "admin"}, format="json")
        self.assertEqual(promote.status_code, 400)
        self.agent_a.refresh_from_db()
        self.assertEqual(self.agent_a.role, "agent")

    def test_admin_resets_password_and_there_is_no_delete(self):
        self.as_user(self.admin)
        response = self.client.patch(
            f"/api/v1/users/{self.agent_b.id}/", {"password": "New-Pass-2026!"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.agent_b.refresh_from_db()
        self.assertTrue(self.agent_b.check_password("New-Pass-2026!"))
        self.assertEqual(self.client.delete(f"/api/v1/users/{self.agent_b.id}/").status_code, 405)
        self.assertTrue(User.objects.filter(pk=self.agent_b.pk).exists())

    def test_tenants_list_is_scoped(self):
        self.as_user(self.coop_admin)
        names = [row["name"] for row in self.client.get("/api/v1/tenants/").data["results"]]
        self.assertEqual(names, ["Coop A"])
