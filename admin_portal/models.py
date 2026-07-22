import uuid

from django.db import models
from django.db.models import Q


class AdminStaffAccess(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ATTENDANT = "attendant", "Attendant"

    customer = models.OneToOneField(
        "customers.CustomerProfile",
        on_delete=models.CASCADE,
        related_name="admin_staff_access",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["customer__email"]
        verbose_name = "admin staff access"
        verbose_name_plural = "admin staff access"

    def __str__(self) -> str:
        return f"{self.customer.email} ({self.role})"


class ImageGenerationBatch(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        READY_FOR_REVIEW = "ready_for_review", "Ready for review"
        PARTIALLY_FAILED = "partially_failed", "Partially failed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.QUEUED)
    provider = models.CharField(max_length=40, default="cloudflare")
    model = models.CharField(max_length=160)
    requested_by = models.ForeignKey(
        "customers.CustomerProfile",
        on_delete=models.PROTECT,
        related_name="image_generation_batches",
    )
    product_count = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ProductImageGeneration(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        GENERATING = "generating", "Generating"
        READY_FOR_REVIEW = "ready_for_review", "Ready for review"
        NEEDS_REGENERATION = "needs_regeneration", "Needs regeneration"
        APPROVED = "approved", "Approved"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    ACTIVE_STATUSES = (
        Status.QUEUED,
        Status.GENERATING,
        Status.READY_FOR_REVIEW,
        Status.NEEDS_REGENERATION,
        Status.APPROVED,
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        ImageGenerationBatch,
        on_delete=models.CASCADE,
        related_name="generations",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="image_generations",
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.QUEUED)
    source_snapshot = models.JSONField(default=dict)
    previous_images = models.JSONField(default=list)
    model = models.CharField(max_length=160)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=80, blank=True)
    last_error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=Q(
                    status__in=(
                        "queued",
                        "generating",
                        "ready_for_review",
                        "needs_regeneration",
                        "approved",
                    )
                ),
                name="unique_active_product_image_generation",
            ),
        ]


class ProductImageCandidate(models.Model):
    class ShotType(models.TextChoices):
        HERO = "hero", "Hero"
        ALTERNATE = "alternate", "Alternate"
        DETAIL = "detail", "Detail"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        GENERATING = "generating", "Generating"
        READY = "ready", "Ready"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generation = models.ForeignKey(
        ProductImageGeneration,
        on_delete=models.CASCADE,
        related_name="candidates",
    )
    shot_type = models.CharField(max_length=20, choices=ShotType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    prompt = models.TextField(blank=True)
    prompt_policy_version = models.CharField(max_length=40, default="v1-automatic")
    regeneration_revision = models.PositiveIntegerField(default=0)
    manual_overrides = models.JSONField(default=dict)
    seed = models.PositiveBigIntegerField()
    storage_path = models.CharField(max_length=500, blank=True)
    public_url = models.URLField(max_length=1000, blank=True)
    mime_type = models.CharField(max_length=80, default="image/webp")
    width = models.PositiveIntegerField(default=768)
    height = models.PositiveIntegerField(default=1024)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    last_error_code = models.CharField(max_length=80, blank=True)
    last_error_message = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        "customers.CustomerProfile",
        on_delete=models.SET_NULL,
        related_name="reviewed_image_candidates",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["generation__created_at", "shot_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["generation", "shot_type"],
                name="unique_generation_candidate_shot",
            ),
        ]
