from django.db import migrations, models


def backfill_published_generation_modes(apps, schema_editor):
    ProductImageGeneration = apps.get_model(
        "admin_portal",
        "ProductImageGeneration",
    )
    ProductImageGeneration.objects.filter(status="published").update(
        publication_mode="replace",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("admin_portal", "0003_candidate_prompt_audit"),
    ]

    operations = [
        migrations.AddField(
            model_name="productimagegeneration",
            name="publication_mode",
            field=models.CharField(
                blank=True,
                choices=[("append", "Append"), ("replace", "Replace")],
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_published_generation_modes,
            migrations.RunPython.noop,
        ),
    ]
