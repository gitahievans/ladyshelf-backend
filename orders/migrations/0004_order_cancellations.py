from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0001_initial"),
        ("orders", "0003_order_payment_expiry"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="cancelled_quantity",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="OrderCancellation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source",
                    models.CharField(
                        choices=[("customer", "Customer"), ("staff", "Staff")],
                        default="customer",
                        max_length=20,
                    ),
                ),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("ordered_by_mistake", "Ordered by mistake"),
                            ("changed_mind", "Changed my mind"),
                            ("wrong_size_or_color", "Need a different size or color"),
                            ("delivery_timing", "Delivery timing no longer works"),
                            ("found_another_option", "Found another option"),
                            ("other", "Other"),
                        ],
                        max_length=40,
                    ),
                ),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="order_cancellations",
                        to="customers.customerprofile",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cancellations",
                        to="orders.order",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="OrderCancellationItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price", models.PositiveIntegerField()),
                ("line_total", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "cancellation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="orders.ordercancellation",
                    ),
                ),
                (
                    "order_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cancellation_items",
                        to="orders.orderitem",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
    ]
