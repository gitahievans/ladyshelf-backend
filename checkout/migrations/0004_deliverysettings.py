from django.db import migrations, models


def seed_delivery_settings(apps, schema_editor):
    DeliverySettings = apps.get_model("checkout", "DeliverySettings")

    DeliverySettings.objects.get_or_create(
        name="Primary Delivery Settings",
        defaults={
            "shop_name": "Wahi Fashion Roysambu",
            "shop_county": "Nairobi",
            "shop_town": "Roysambu",
            "shop_street_address": "Lumumba Drive, Roysambu",
            "shop_latitude": "-1.218257",
            "shop_longitude": "36.886459",
            "rider_max_radius_km": 50,
            "parcel_switch_radius_km": 50,
            "rider_base_fee": 200,
            "rider_increment_per_10km": 200,
            "rider_estimated_window": "2-3 business days",
            "parcel_estimated_window": "Dispatch arranged after payment confirmation",
            "allow_pay_on_delivery": True,
            "parcel_manual_fee_confirmation_required": True,
            "is_active": True,
        },
    )


def unseed_delivery_settings(apps, schema_editor):
    DeliverySettings = apps.get_model("checkout", "DeliverySettings")
    DeliverySettings.objects.filter(name="Primary Delivery Settings").delete()


class Migration(migrations.Migration):
    dependencies = [("checkout", "0003_update_parcel_zone_rules")]

    operations = [
        migrations.CreateModel(
            name="DeliverySettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="Primary Delivery Settings", max_length=120)),
                ("shop_name", models.CharField(default="Wahi Fashion Roysambu", max_length=120)),
                ("shop_county", models.CharField(default="Nairobi", max_length=120)),
                ("shop_town", models.CharField(default="Roysambu", max_length=120)),
                ("shop_street_address", models.CharField(default="Lumumba Drive, Roysambu", max_length=255)),
                ("shop_latitude", models.DecimalField(decimal_places=6, max_digits=9)),
                ("shop_longitude", models.DecimalField(decimal_places=6, max_digits=9)),
                ("rider_max_radius_km", models.PositiveIntegerField(default=50)),
                ("parcel_switch_radius_km", models.PositiveIntegerField(default=50)),
                ("rider_base_fee", models.PositiveIntegerField(default=200)),
                ("rider_increment_per_10km", models.PositiveIntegerField(default=200)),
                ("rider_estimated_window", models.CharField(default="2-3 business days", max_length=120)),
                (
                    "parcel_estimated_window",
                    models.CharField(default="Dispatch arranged after payment confirmation", max_length=120),
                ),
                ("allow_pay_on_delivery", models.BooleanField(default=True)),
                ("parcel_manual_fee_confirmation_required", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.RunPython(seed_delivery_settings, unseed_delivery_settings),
    ]
