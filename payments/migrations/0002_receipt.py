from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0001_initial"),
        ("orders", "0003_order_payment_expiry"),
        ("payments", "0001_paymenttransaction"),
    ]

    operations = [
        migrations.CreateModel(
            name="Receipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("receipt_number", models.CharField(max_length=40, unique=True)),
                ("status", models.CharField(choices=[("issued", "Issued"), ("sent", "Sent"), ("failed", "Failed")], default="issued", max_length=20)),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("sent_to_email", models.EmailField(blank=True, max_length=254)),
                ("total_paid", models.PositiveIntegerField()),
                ("currency", models.CharField(default="KES", max_length=3)),
                ("payment_method", models.CharField(choices=[("mpesa", "M-Pesa"), ("card", "Card")], max_length=20)),
                ("payment_reference", models.CharField(blank=True, max_length=120)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_receipts", to="customers.customerprofile")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="receipt", to="orders.order")),
                ("payment_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="receipts", to="payments.paymenttransaction")),
            ],
            options={
                "ordering": ["-issued_at", "-id"],
            },
        ),
    ]
