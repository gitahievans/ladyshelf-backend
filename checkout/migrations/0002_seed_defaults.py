from django.db import migrations


def seed_checkout_defaults(apps, schema_editor):
    DeliveryZone = apps.get_model("checkout", "DeliveryZone")
    PickupLocation = apps.get_model("checkout", "PickupLocation")

    PickupLocation.objects.get_or_create(
        name="Wahi Fashion Roysambu Pickup",
        defaults={
            "county": "Nairobi",
            "town": "Roysambu",
            "street_address": "Lumumba Drive, Roysambu",
            "contact_name": "Wahi Fashion",
            "contact_phone": "+254711000000",
            "maps_url": "https://maps.google.com/?q=Lumumba+Drive+Roysambu",
            "opening_hours": "Mon-Sat 9am-7pm",
            "collection_window_hours": 72,
            "notes": "Collect within 72 hours after confirmation.",
            "is_active": True,
        },
    )

    DeliveryZone.objects.get_or_create(
        name="Nairobi Rider Zone",
        defaults={
            "delivery_mode": "rider",
            "counties": ["Nairobi"],
            "towns": ["Roysambu", "Westlands", "Kilimani", "Kasarani", "Parklands"],
            "delivery_fee": 300,
            "manual_fee_confirmation_required": False,
            "allow_pay_on_delivery": True,
            "estimated_window": "2-3 business days",
            "priority": 10,
            "is_active": True,
        },
    )

    DeliveryZone.objects.get_or_create(
        name="Nearby Towns Rider Zone",
        defaults={
            "delivery_mode": "rider",
            "counties": ["Kiambu", "Machakos", "Kajiado"],
            "towns": ["Thika", "Athi River", "Kitengela", "Ruiru", "Kiambu"],
            "delivery_fee": 450,
            "manual_fee_confirmation_required": False,
            "allow_pay_on_delivery": True,
            "estimated_window": "2-3 business days",
            "priority": 20,
            "is_active": True,
        },
    )

    DeliveryZone.objects.get_or_create(
        name="Rest of Kenya Parcel Zone",
        defaults={
            "delivery_mode": "parcel",
            "counties": [],
            "towns": [],
            "delivery_fee": 0,
            "manual_fee_confirmation_required": False,
            "allow_pay_on_delivery": False,
            "estimated_window": "3-5 business days",
            "priority": 100,
            "is_active": True,
        },
    )


def unseed_checkout_defaults(apps, schema_editor):
    DeliveryZone = apps.get_model("checkout", "DeliveryZone")
    PickupLocation = apps.get_model("checkout", "PickupLocation")

    DeliveryZone.objects.filter(
        name__in=[
            "Nairobi Rider Zone",
            "Nearby Towns Rider Zone",
            "Rest of Kenya Parcel Zone",
        ]
    ).delete()
    PickupLocation.objects.filter(name="Wahi Fashion Roysambu Pickup").delete()


class Migration(migrations.Migration):
    dependencies = [("checkout", "0001_initial")]

    operations = [migrations.RunPython(seed_checkout_defaults, unseed_checkout_defaults)]
