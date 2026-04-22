from django.contrib.auth.models import Group
from django.core.cache import cache
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework.settings import api_settings

from common.admin_roles import ATTENDANT_GROUP_NAME, OWNER_GROUP_NAME, bootstrap_admin_groups
from checkout.views import CheckoutQuoteView


class HealthCheckViewTests(TestCase):
    def test_health_check_returns_ok(self):
        response = self.client.get(reverse("health-check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class AdminRoleBootstrapTests(TestCase):
    def test_bootstrap_admin_groups_creates_owner_and_attendant_roles(self):
        role_counts = bootstrap_admin_groups()

        owner_group = Group.objects.get(name=OWNER_GROUP_NAME)
        attendant_group = Group.objects.get(name=ATTENDANT_GROUP_NAME)

        self.assertGreater(role_counts[OWNER_GROUP_NAME], 0)
        self.assertGreater(role_counts[ATTENDANT_GROUP_NAME], 0)
        self.assertTrue(owner_group.permissions.filter(codename="change_order").exists())
        self.assertTrue(attendant_group.permissions.filter(codename="view_paymenttransaction").exists())
        self.assertFalse(attendant_group.permissions.filter(codename="delete_paymenttransaction").exists())


class ThrottlingTests(TestCase):
    def test_checkout_quote_view_uses_scoped_throttle_configuration(self):
        cache.clear()

        self.assertEqual(CheckoutQuoteView.throttle_scope, "checkout_quote")
        self.assertIn(
            "rest_framework.throttling.ScopedRateThrottle",
            settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"],
        )
        self.assertIn("checkout_quote", settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
        self.assertIn(api_settings.DEFAULT_THROTTLE_CLASSES[-1], CheckoutQuoteView.throttle_classes)

