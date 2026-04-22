from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_phase6_order_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="payment_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
