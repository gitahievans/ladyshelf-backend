from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("admin_portal", "0002_image_generation"),
    ]

    operations = [
        migrations.AddField(
            model_name="productimagecandidate",
            name="manual_overrides",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="productimagecandidate",
            name="prompt_policy_version",
            field=models.CharField(default="v1-automatic", max_length=40),
        ),
        migrations.AddField(
            model_name="productimagecandidate",
            name="regeneration_revision",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
