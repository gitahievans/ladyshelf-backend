from django.db import migrations


def update_parcel_zone_rules(apps, schema_editor):
    DeliveryZone = apps.get_model("checkout", "DeliveryZone")
    DeliveryZone.objects.filter(delivery_mode="parcel").update(
        manual_fee_confirmation_required=False,
        delivery_fee=0,
        allow_pay_on_delivery=False,
        estimated_window="3-5 business days",
    )


class Migration(migrations.Migration):
    dependencies = [("checkout", "0002_seed_defaults")]

    operations = [migrations.RunPython(update_parcel_zone_rules, migrations.RunPython.noop)]
