from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guest_email", models.EmailField(blank=True, max_length=254)),
                ("order_number", models.CharField(max_length=40, unique=True)),
                ("delivery_details", models.JSONField(default=dict)),
                ("subtotal", models.PositiveIntegerField()),
                ("delivery_fee", models.PositiveIntegerField(default=0)),
                ("discount", models.PositiveIntegerField(default=0)),
                ("total", models.PositiveIntegerField()),
                ("currency", models.CharField(choices=[("KES", "KES")], default="KES", max_length=3)),
                (
                    "payment_method",
                    models.CharField(
                        choices=[
                            ("mpesa", "M-Pesa"),
                            ("card", "Card"),
                            ("cash-on-delivery", "Cash on Delivery"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "payment_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("paid", "Paid"),
                            ("failed", "Failed"),
                            ("refunded", "Refunded"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "order_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("confirmed", "Confirmed"),
                            ("processing", "Processing"),
                            ("shipped", "Shipped"),
                            ("delivered", "Delivered"),
                            ("cancelled", "Cancelled"),
                        ],
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="orders",
                        to="customers.customerprofile",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("variant_id", models.CharField(max_length=50)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("product_name", models.CharField(max_length=255)),
                ("product_image", models.URLField()),
                ("price", models.PositiveIntegerField()),
                ("currency", models.CharField(choices=[("KES", "KES")], default="KES", max_length=3)),
                ("size", models.CharField(max_length=20)),
                ("color", models.CharField(max_length=120)),
                ("color_hex", models.CharField(max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="items", to="orders.order"),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="order_items",
                        to="catalog.product",
                    ),
                ),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
