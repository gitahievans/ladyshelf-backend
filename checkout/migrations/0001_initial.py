from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DeliveryZone",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                (
                    "delivery_mode",
                    models.CharField(
                        choices=[("rider", "Rider"), ("parcel", "Parcel")],
                        max_length=20,
                    ),
                ),
                ("counties", models.JSONField(blank=True, default=list)),
                ("towns", models.JSONField(blank=True, default=list)),
                ("delivery_fee", models.PositiveIntegerField(default=0)),
                ("manual_fee_confirmation_required", models.BooleanField(default=False)),
                ("allow_pay_on_delivery", models.BooleanField(default=False)),
                ("estimated_window", models.CharField(blank=True, max_length=120)),
                ("priority", models.PositiveIntegerField(default=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["priority", "name"]},
        ),
        migrations.CreateModel(
            name="PickupLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("county", models.CharField(max_length=120)),
                ("town", models.CharField(max_length=120)),
                ("street_address", models.CharField(max_length=255)),
                ("contact_name", models.CharField(blank=True, max_length=120)),
                ("contact_phone", models.CharField(max_length=30)),
                ("maps_url", models.URLField()),
                ("opening_hours", models.CharField(blank=True, max_length=120)),
                ("collection_window_hours", models.PositiveIntegerField(default=72)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
    ]
