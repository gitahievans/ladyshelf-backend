from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("orders", "0002_phase6_order_workflow"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("sasapay", "SasaPay")], default="sasapay", max_length=30)),
                ("payment_method", models.CharField(choices=[("mpesa", "M-Pesa"), ("card", "Card")], max_length=20)),
                ("status", models.CharField(choices=[("initiated", "Initiated"), ("pending", "Pending"), ("paid", "Paid"), ("failed", "Failed")], default="initiated", max_length=20)),
                ("amount", models.PositiveIntegerField()),
                ("currency", models.CharField(default="KES", max_length=3)),
                ("merchant_reference", models.CharField(db_index=True, max_length=80)),
                ("merchant_request_id", models.CharField(blank=True, db_index=True, max_length=120)),
                ("checkout_request_id", models.CharField(blank=True, db_index=True, max_length=120)),
                ("transaction_code", models.CharField(blank=True, db_index=True, max_length=120)),
                ("checkout_url", models.URLField(blank=True)),
                ("provider_response", models.JSONField(blank=True, default=dict)),
                ("callback_payload", models.JSONField(blank=True, default=dict)),
                ("last_status_payload", models.JSONField(blank=True, default=dict)),
                ("verification_payload", models.JSONField(blank=True, default=dict)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payment_transactions",
                        to="orders.order",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
