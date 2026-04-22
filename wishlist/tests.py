from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Product
from customers.models import CustomerProfile
from wishlist.models import WishlistItem


class WishlistApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = CustomerProfile.objects.create(
            supabase_user_id="wishlist-user-1",
            email="wishlist@example.com",
            first_name="Wanja",
            last_name="Njeri",
        )
        self.product = Product.objects.get(slug="obsidian-power-blazer")

    def test_authenticated_user_can_add_and_list_wishlist_items(self):
        self.client.force_authenticate(user=self.customer)

        create_response = self.client.post(
            "/api/v1/wishlist/",
            {"productId": self.product.external_id},
            format="json",
        )
        list_response = self.client.get("/api/v1/wishlist/")

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["productIds"], [self.product.external_id])
        self.assertEqual(WishlistItem.objects.count(), 1)

    def test_authenticated_user_can_remove_and_clear_wishlist_items(self):
        WishlistItem.objects.create(customer=self.customer, product=self.product)
        self.client.force_authenticate(user=self.customer)

        remove_response = self.client.delete(
            f"/api/v1/wishlist/{self.product.external_id}"
        )
        WishlistItem.objects.create(customer=self.customer, product=self.product)
        clear_response = self.client.delete("/api/v1/wishlist/")

        self.assertEqual(remove_response.status_code, 204)
        self.assertEqual(clear_response.status_code, 204)
        self.assertEqual(WishlistItem.objects.count(), 0)
