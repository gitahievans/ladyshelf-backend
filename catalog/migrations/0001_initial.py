import json
from pathlib import Path

from django.db import migrations, models


def seed_catalog(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")
    ProductVariant = apps.get_model("catalog", "ProductVariant")

    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "catalog_seed.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    categories_by_slug = {}
    for category_data in payload["categories"]:
        category = Category.objects.create(
            external_id=category_data["id"],
            slug=category_data["slug"],
            name=category_data["name"],
            description=category_data["description"],
            image=category_data["image"],
        )
        categories_by_slug[category.slug] = category

    for product_data in payload["products"]:
        product = Product.objects.create(
            external_id=product_data["id"],
            slug=product_data["slug"],
            name=product_data["name"],
            brand=product_data["brand"],
            category=categories_by_slug[product_data["categorySlug"]],
            description=product_data["description"],
            images=product_data["images"],
            price=product_data["price"],
            original_price=product_data.get("originalPrice"),
            currency=product_data["currency"],
            badge=product_data.get("badge"),
            tags=product_data["tags"],
            rating=product_data["rating"],
            review_count=product_data["reviewCount"],
            is_featured=product_data["isFeatured"],
            is_new_arrival=product_data["isNewArrival"],
            material=product_data.get("material", ""),
            care_instructions=product_data.get("careInstructions", ""),
            created_at=product_data["createdAt"],
        )

        for variant_data in product_data["variants"]:
            ProductVariant.objects.create(
                external_id=variant_data["id"],
                product=product,
                size=variant_data["size"],
                color=variant_data["color"],
                color_hex=variant_data["colorHex"],
                stock=variant_data["stock"],
                sku=variant_data["sku"],
            )


def unseed_catalog(apps, schema_editor):
    ProductVariant = apps.get_model("catalog", "ProductVariant")
    Product = apps.get_model("catalog", "Product")
    Category = apps.get_model("catalog", "Category")

    ProductVariant.objects.all().delete()
    Product.objects.all().delete()
    Category.objects.all().delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=50, unique=True)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField()),
                ("image", models.URLField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"], "verbose_name_plural": "categories"},
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=50, unique=True)),
                ("slug", models.SlugField(max_length=160, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("brand", models.CharField(default="Wahi Fashion", max_length=120)),
                ("description", models.TextField()),
                ("images", models.JSONField(default=list)),
                ("price", models.PositiveIntegerField()),
                ("original_price", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "currency",
                    models.CharField(
                        choices=[("KES", "KES")],
                        default="KES",
                        max_length=3,
                    ),
                ),
                (
                    "badge",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("new", "New"),
                            ("sale", "Sale"),
                            ("bestseller", "Bestseller"),
                            ("limited", "Limited"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("tags", models.JSONField(default=list)),
                ("rating", models.DecimalField(decimal_places=2, default=0, max_digits=3)),
                ("review_count", models.PositiveIntegerField(default=0)),
                ("is_featured", models.BooleanField(default=False)),
                ("is_new_arrival", models.BooleanField(default=False)),
                ("material", models.TextField(blank=True)),
                ("care_instructions", models.TextField(blank=True)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="products", to="catalog.category"),
                ),
            ],
            options={"ordering": ["-created_at", "name"]},
        ),
        migrations.CreateModel(
            name="ProductVariant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=50, unique=True)),
                ("size", models.CharField(max_length=20)),
                ("color", models.CharField(max_length=120)),
                ("color_hex", models.CharField(max_length=20)),
                ("stock", models.PositiveIntegerField(default=0)),
                ("sku", models.CharField(max_length=80, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="variants", to="catalog.product"),
                ),
            ],
            options={"ordering": ["product__name", "color", "size", "sku"]},
        ),
        migrations.RunPython(seed_catalog, reverse_code=unseed_catalog),
    ]
