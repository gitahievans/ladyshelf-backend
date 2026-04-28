from unittest.mock import patch

from django.test import TestCase
from rest_framework import exceptions
from rest_framework.test import APIClient

from customers.auth import SupabaseJWTAuthentication
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

    def test_authenticated_user_can_update_phone(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            "/api/v1/account/me",
            {
                "phone": " +254711223344 ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.phone, "+254711223344")
        self.assertEqual(response.json()["phone"], "+254711223344")

    def test_authenticated_user_can_update_name_and_phone(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            "/api/v1/account/me",
            {
                "firstName": " Amina ",
                "lastName": " Njeri ",
                "phone": " +254722334455 ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Amina")
        self.assertEqual(self.customer.last_name, "Njeri")
        self.assertEqual(self.customer.phone, "+254722334455")
        self.assertEqual(response.json()["firstName"], "Amina")
        self.assertEqual(response.json()["lastName"], "Njeri")
        self.assertEqual(response.json()["phone"], "+254722334455")

    def test_blank_phone_is_rejected(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            "/api/v1/account/me",
            {
                "phone": "   ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.phone, "")

    def test_blank_first_name_is_rejected(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            "/api/v1/account/me",
            {
                "firstName": "   ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Asha")

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

    def test_existing_profile_edits_are_not_overwritten_by_claims(self):
        customer = CustomerProfile.objects.create(
            supabase_user_id="supabase-user-2",
            email="customer2@example.com",
            first_name="Edited",
            last_name="Profile",
            phone="+254799000111",
        )
        payload = {
            "sub": "supabase-user-2",
            "email": "customer2@example.com",
            "email_confirmed_at": None,
            "user_metadata": {
                "first_name": "Token",
                "last_name": "Name",
                "phone": "+254700000000",
            },
        }

        resolved_customer = SupabaseJWTAuthentication()._get_or_create_customer(payload)

        customer.refresh_from_db()
        self.assertEqual(resolved_customer.pk, customer.pk)
        self.assertEqual(customer.first_name, "Edited")
        self.assertEqual(customer.last_name, "Profile")
        self.assertEqual(customer.phone, "+254799000111")

    def test_blank_profile_fields_can_still_be_backfilled_from_claims(self):
        customer = CustomerProfile.objects.create(
            supabase_user_id="supabase-user-3",
            email="customer3@example.com",
            first_name="",
            last_name="",
            phone="",
        )
        payload = {
            "sub": "supabase-user-3",
            "email": "customer3@example.com",
            "email_confirmed_at": None,
            "user_metadata": {
                "first_name": "Token",
                "last_name": "Backfill",
                "phone": "+254711000222",
            },
        }

        SupabaseJWTAuthentication()._get_or_create_customer(payload)

        customer.refresh_from_db()
        self.assertEqual(customer.first_name, "Token")
        self.assertEqual(customer.last_name, "Backfill")
        self.assertEqual(customer.phone, "+254711000222")

# Create your tests here.
