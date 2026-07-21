from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_productvariant_image_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="is_published",
            field=models.BooleanField(db_index=True, default=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="product",
            name="is_published",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
