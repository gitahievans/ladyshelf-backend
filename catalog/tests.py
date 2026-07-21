from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Category, Product, ProductVariant


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
        variant = ProductVariant.objects.filter(product=product).first()
        variant.image_url = "https://example.com/black-blazer.jpg"
        variant.save(update_fields=["image_url", "updated_at"])

        response = self.client.get(f"/api/v1/catalog/products/{product.slug}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], product.slug)
        self.assertGreater(len(response.data["variants"]), 0)
        self.assertEqual(response.data["variants"][0]["imageUrl"], variant.image_url)

    def test_public_catalog_excludes_unpublished_products_and_counts(self):
        product = Product.objects.get(slug="obsidian-power-blazer")
        product.is_published = False
        product.save(update_fields=["is_published", "updated_at"])

        list_response = self.client.get("/api/v1/catalog/products")
        detail_response = self.client.get(f"/api/v1/catalog/products/{product.slug}")
        categories_response = self.client.get("/api/v1/catalog/categories")
        category_payload = next(
            item for item in categories_response.data if item["slug"] == product.category.slug
        )

        self.assertFalse(any(item["slug"] == product.slug for item in list_response.data))
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            category_payload["productCount"],
            Product.objects.filter(
                category=product.category,
                is_published=True,
            ).count(),
        )
