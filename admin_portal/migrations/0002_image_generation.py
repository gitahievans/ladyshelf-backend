import django.db.models.deletion
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("admin_portal", "0001_initial"),
        ("catalog", "0003_product_is_published"),
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImageGenerationBatch",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("processing", "Processing"), ("ready_for_review", "Ready for review"), ("partially_failed", "Partially failed"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="queued", max_length=30)),
                ("provider", models.CharField(default="cloudflare", max_length=40)),
                ("model", models.CharField(max_length=160)),
                ("product_count", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="image_generation_batches", to="customers.customerprofile")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ProductImageGeneration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("generating", "Generating"), ("ready_for_review", "Ready for review"), ("needs_regeneration", "Needs regeneration"), ("approved", "Approved"), ("published", "Published"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="queued", max_length=30)),
                ("source_snapshot", models.JSONField(default=dict)),
                ("previous_images", models.JSONField(default=list)),
                ("model", models.CharField(max_length=160)),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=80)),
                ("last_error_message", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="generations", to="admin_portal.imagegenerationbatch")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="image_generations", to="catalog.product")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="ProductImageCandidate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("shot_type", models.CharField(choices=[("hero", "Hero"), ("alternate", "Alternate"), ("detail", "Detail")], max_length=20)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("generating", "Generating"), ("ready", "Ready"), ("approved", "Approved"), ("rejected", "Rejected"), ("failed", "Failed")], default="queued", max_length=20)),
                ("prompt", models.TextField(blank=True)),
                ("seed", models.PositiveBigIntegerField()),
                ("storage_path", models.CharField(blank=True, max_length=500)),
                ("public_url", models.URLField(blank=True, max_length=1000)),
                ("mime_type", models.CharField(default="image/webp", max_length=80)),
                ("width", models.PositiveIntegerField(default=768)),
                ("height", models.PositiveIntegerField(default=1024)),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("last_error_code", models.CharField(blank=True, max_length=80)),
                ("last_error_message", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("generation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="candidates", to="admin_portal.productimagegeneration")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_image_candidates", to="customers.customerprofile")),
            ],
            options={"ordering": ["generation__created_at", "shot_type"]},
        ),
        migrations.AddConstraint(
            model_name="productimagegeneration",
            constraint=models.UniqueConstraint(condition=models.Q(("status__in", ("queued", "generating", "ready_for_review", "needs_regeneration", "approved"))), fields=("product",), name="unique_active_product_image_generation"),
        ),
        migrations.AddConstraint(
            model_name="productimagecandidate",
            constraint=models.UniqueConstraint(fields=("generation", "shot_type"), name="unique_generation_candidate_shot"),
        ),
    ]
