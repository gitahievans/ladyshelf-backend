from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Category, Product


class CatalogApiTests(APITestCase):
    def test_category_list_returns_seeded_categories(self):
        response = self.client.get("/api/v1/catalog/categories")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), Category.objects.count())
        self.assertEqual(response.data[0]["productCount"], 4)

    def test_product_list_supports_category_and_sort_filters(self):
        response = self.client.get(
            "/api/v1/catalog/products",
            {"category": "accessories", "sort": "price-desc"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)
        self.assertGreaterEqual(response.data[0]["price"], response.data[1]["price"])
        self.assertTrue(
            all(product["categorySlug"] == "accessories" for product in response.data)
        )

    def test_product_list_supports_search_and_out_of_stock_items_remain_visible(self):
        response = self.client.get("/api/v1/catalog/products", {"q": "ankara"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any("ankara" in product["slug"] for product in response.data))

    def test_product_detail_returns_variants(self):
        product = Product.objects.get(slug="obsidian-power-blazer")

        response = self.client.get(f"/api/v1/catalog/products/{product.slug}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], product.slug)
        self.assertGreater(len(response.data["variants"]), 0)
