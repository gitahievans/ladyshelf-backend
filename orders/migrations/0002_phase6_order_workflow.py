from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="order",
            name="payment_method",
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_mode",
            field=models.CharField(
                blank=True,
                choices=[("rider", "Rider"), ("parcel", "Parcel"), ("pickup", "Pickup")],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="internal_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="order",
            name="manual_delivery_fee_confirmation_required",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                choices=[("mpesa", "M-Pesa"), ("card", "Card")],
                default="mpesa",
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="order",
            name="payment_timing",
            field=models.CharField(
                choices=[("prepay", "Prepay"), ("pay_on_delivery", "Pay on Delivery")],
                default="prepay",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_instructions",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name="order",
            name="order_status",
            field=models.CharField(
                choices=[
                    ("new", "New"),
                    ("awaiting_payment", "Awaiting Payment"),
                    ("paid", "Paid"),
                    (
                        "awaiting_delivery_fee_confirmation",
                        "Awaiting Delivery Fee Confirmation",
                    ),
                    ("ready_for_dispatch", "Ready for Dispatch"),
                    ("out_for_delivery", "Out for Delivery"),
                    ("ready_for_pickup", "Ready for Pickup"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                ],
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("paid", "Paid"),
                    ("failed", "Failed"),
                    ("manual_on_delivery", "Manual on Delivery"),
                    ("refunded", "Refunded"),
                ],
                max_length=20,
            ),
        ),
    ]
