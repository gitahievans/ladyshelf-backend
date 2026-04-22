from unittest.mock import patch

from django.test import TestCase
from rest_framework import exceptions
from rest_framework.test import APIClient

from customers.models import Address, CustomerProfile


class AccountEndpointsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = CustomerProfile.objects.create(
            supabase_user_id="supabase-user-1",
            email="customer@example.com",
            first_name="Asha",
            last_name="Kamau",
        )

    def test_me_returns_customer_profile(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get("/api/v1/account/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "customer@example.com")
        self.assertEqual(response.json()["firstName"], "Asha")

    def test_authenticated_user_can_create_address(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            "/api/v1/account/addresses",
            {
                "label": "home",
                "fullName": "Asha Kamau",
                "phone": "+254700000000",
                "county": "Nairobi",
                "town": "Roysambu",
                "streetAddress": "Lumumba Drive",
                "additionalInfo": "Gate 2",
                "isDefault": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Address.objects.count(), 1)
        self.assertEqual(Address.objects.get().customer, self.customer)


class SupabaseAuthenticationTests(TestCase):
    def test_invalid_token_is_rejected(self):
        client = APIClient()

        with patch(
            "customers.auth.SupabaseJWTAuthentication._decode_token",
            side_effect=exceptions.AuthenticationFailed("Invalid Supabase access token."),
        ):
            response = client.get("/api/v1/account/me", HTTP_AUTHORIZATION="Bearer bad-token")

        self.assertEqual(response.status_code, 403)

# Create your tests here.
