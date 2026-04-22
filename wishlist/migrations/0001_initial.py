from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="WishlistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "customer",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="wishlist_items", to="customers.customerprofile"),
                ),
                (
                    "product",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="wishlist_items", to="catalog.product"),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="wishlistitem",
            constraint=models.UniqueConstraint(
                fields=("customer", "product"),
                name="unique_customer_wishlist_product",
            ),
        ),
    ]
