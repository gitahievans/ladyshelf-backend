from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from admin_portal.image_generation.cloudflare import (
    ImageProviderError,
    build_reference_image,
    generate_image,
    prepare_candidate_image,
)
from admin_portal.image_generation.prompts import (
    PROMPT_POLICY_V2,
    build_prompt,
    deterministic_seed,
    resolve_shot_overrides,
)
from admin_portal.image_generation.storage import (
    ImageStorageError,
    SupabaseImageStorage,
    draft_path,
    published_path,
)
from admin_portal.models import (
    ImageGenerationBatch,
    ProductImageCandidate,
    ProductImageGeneration,
)
from catalog.models import Product, ProductVariant


SHOT_ORDER = (
    ProductImageCandidate.ShotType.HERO,
    ProductImageCandidate.ShotType.ALTERNATE,
    ProductImageCandidate.ShotType.DETAIL,
)
MAX_ATTEMPTS = 3


class ImageGenerationWorkflowError(Exception):
    def __init__(self, code: str, safe_message: str):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


def product_snapshot(product: Product) -> dict:
    colors = sorted(
        {
            color.strip()
            for color in product.variants.values_list("color", flat=True)
            if color.strip()
        }
    )
    return {
        "id": str(product.pk),
        "name": product.name,
        "slug": product.slug,
        "description": product.description,
        "category": product.category.name,
        "material": product.material,
        "tags": list(product.tags),
        "colors": colors,
    }


@transaction.atomic
def create_batch(*, product_ids: list[int], requested_by) -> ImageGenerationBatch:
    if not settings.IMAGE_GENERATION_ENABLED:
        raise ImageGenerationWorkflowError("generation_disabled", "Image generation is currently disabled.")
    if not 1 <= len(product_ids) <= 5:
        raise ImageGenerationWorkflowError("invalid_batch_size", "Select between one and five products.")
    if len(set(product_ids)) != len(product_ids):
        raise ImageGenerationWorkflowError("duplicate_products", "Select each product only once.")

    products = list(
        Product.objects.select_for_update()
        .select_related("category")
        .prefetch_related("variants")
        .filter(pk__in=product_ids)
    )
    if len(products) != len(product_ids):
        raise ImageGenerationWorkflowError("unknown_products", "One or more selected products no longer exist.")
    active_ids = set(
        ProductImageGeneration.objects.filter(
            product_id__in=product_ids,
            status__in=ProductImageGeneration.ACTIVE_STATUSES,
        ).values_list("product_id", flat=True)
    )
    if active_ids:
        raise ImageGenerationWorkflowError("active_generation", "A selected product already has active image-generation work.")

    products_by_id = {product.pk: product for product in products}
    batch = ImageGenerationBatch.objects.create(
        requested_by=requested_by,
        product_count=len(product_ids),
        model=settings.CLOUDFLARE_IMAGE_MODEL,
    )
    for product_id in product_ids:
        product = products_by_id[product_id]
        snapshot = product_snapshot(product)
        if not snapshot["colors"]:
            raise ImageGenerationWorkflowError(
                "missing_variant_color",
                f"{product.name} needs at least one colored variant before AI images can be generated.",
            )
        overrides_by_shot = resolve_shot_overrides(
            snapshot,
            {shot_type: {} for shot_type in SHOT_ORDER},
        )
        generation = ProductImageGeneration.objects.create(
            batch=batch,
            product=product,
            source_snapshot=snapshot,
            model=settings.CLOUDFLARE_IMAGE_MODEL,
        )
        for shot_type in SHOT_ORDER:
            ProductImageCandidate.objects.create(
                generation=generation,
                shot_type=shot_type,
                prompt=build_prompt(
                    snapshot,
                    shot_type,
                    overrides_by_shot[shot_type],
                    policy_version=PROMPT_POLICY_V2,
                ),
                prompt_policy_version=PROMPT_POLICY_V2,
                manual_overrides=overrides_by_shot[shot_type],
                seed=deterministic_seed(str(product.pk), shot_type, 0),
            )
    return batch


def recompute_batch(batch_id: object) -> None:
    batch = ImageGenerationBatch.objects.get(pk=batch_id)
    statuses = list(batch.generations.values_list("status", flat=True))
    if not statuses:
        batch.status = ImageGenerationBatch.Status.CANCELLED
        batch.completed_at = timezone.now()
        batch.save(update_fields=["status", "completed_at", "updated_at"])
        return
    terminal = {
        ProductImageGeneration.Status.PUBLISHED,
        ProductImageGeneration.Status.CANCELLED,
    }
    if statuses and all(status in terminal for status in statuses):
        batch.status = (
            ImageGenerationBatch.Status.COMPLETED
            if ProductImageGeneration.Status.PUBLISHED in statuses
            else ImageGenerationBatch.Status.CANCELLED
        )
        batch.completed_at = timezone.now()
    elif any(
        status in {ProductImageGeneration.Status.FAILED, ProductImageGeneration.Status.NEEDS_REGENERATION}
        for status in statuses
    ):
        batch.status = ImageGenerationBatch.Status.PARTIALLY_FAILED
        batch.completed_at = None
    elif any(
        status in {ProductImageGeneration.Status.QUEUED, ProductImageGeneration.Status.GENERATING}
        for status in statuses
    ):
        batch.status = (
            ImageGenerationBatch.Status.QUEUED
            if statuses and all(status == ProductImageGeneration.Status.QUEUED for status in statuses)
            else ImageGenerationBatch.Status.PROCESSING
        )
        batch.completed_at = None
    else:
        batch.status = ImageGenerationBatch.Status.READY_FOR_REVIEW
        batch.completed_at = None
    batch.save(update_fields=["status", "completed_at", "updated_at"])


def _next_midnight_utc() -> datetime:
    now = datetime.now(UTC)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)


def _retry_time(attempt_count: int) -> datetime:
    return timezone.now() + timedelta(minutes=min(2 ** max(attempt_count - 1, 0), 15))


def _mark_failure(
    generation: ProductImageGeneration,
    candidate: ProductImageCandidate,
    error: ImageProviderError | ImageStorageError,
) -> None:
    candidate.status = ProductImageCandidate.Status.FAILED
    candidate.last_error_code = error.code
    candidate.last_error_message = error.safe_message
    candidate.save(
        update_fields=["status", "last_error_code", "last_error_message", "updated_at"]
    )
    generation.last_error_code = error.code
    generation.last_error_message = error.safe_message

    if isinstance(error, ImageProviderError) and error.code == "daily_quota":
        candidate.status = ProductImageCandidate.Status.QUEUED
        candidate.save(update_fields=["status", "updated_at"])
        generation.status = ProductImageGeneration.Status.QUEUED
        generation.next_attempt_at = _next_midnight_utc()
    elif isinstance(error, ImageProviderError) and error.retryable and candidate.attempt_count < MAX_ATTEMPTS:
        generation.status = ProductImageGeneration.Status.QUEUED
        generation.next_attempt_at = _retry_time(candidate.attempt_count)
    elif error.code in {"provider_auth", "provider_configuration", "generation_disabled", "storage_configuration"}:
        generation.status = ProductImageGeneration.Status.FAILED
        generation.next_attempt_at = None
    else:
        generation.status = ProductImageGeneration.Status.NEEDS_REGENERATION
        generation.next_attempt_at = None
    generation.save(
        update_fields=[
            "status",
            "next_attempt_at",
            "last_error_code",
            "last_error_message",
            "updated_at",
        ]
    )
    recompute_batch(generation.batch_id)


def _claim_generation() -> ProductImageGeneration | None:
    now = timezone.now()
    with transaction.atomic():
        queryset = ProductImageGeneration.objects.filter(
            status=ProductImageGeneration.Status.QUEUED,
        ).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)).order_by("created_at")
        if connection.features.has_select_for_update_skip_locked:
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        generation = queryset.first()
        if generation is None:
            return None
        generation.status = ProductImageGeneration.Status.GENERATING
        generation.attempt_count += 1
        generation.next_attempt_at = None
        generation.started_at = generation.started_at or now
        generation.last_error_code = ""
        generation.last_error_message = ""
        generation.save(
            update_fields=[
                "status",
                "attempt_count",
                "next_attempt_at",
                "started_at",
                "last_error_code",
                "last_error_message",
                "updated_at",
            ]
        )
        batch = generation.batch
        batch.status = ImageGenerationBatch.Status.PROCESSING
        batch.save(update_fields=["status", "updated_at"])
        return generation


def process_next_generation(*, storage: SupabaseImageStorage | None = None) -> bool:
    generation = _claim_generation()
    if generation is None:
        return False
    candidates = {
        candidate.shot_type: candidate
        for candidate in generation.candidates.all()
    }
    if storage is None:
        try:
            storage = SupabaseImageStorage()
        except ImageStorageError as error:
            _mark_failure(
                generation,
                candidates[ProductImageCandidate.ShotType.HERO],
                error,
            )
            return True
    reference_image: bytes | None = None

    hero = candidates[ProductImageCandidate.ShotType.HERO]
    if hero.status in {ProductImageCandidate.Status.READY, ProductImageCandidate.Status.APPROVED}:
        try:
            reference_image = build_reference_image(storage.download(hero.storage_path))
        except (ImageStorageError, ImageProviderError) as error:
            _mark_failure(generation, hero, error)
            return True

    for shot_type in SHOT_ORDER:
        candidate = candidates[shot_type]
        if candidate.status in {ProductImageCandidate.Status.READY, ProductImageCandidate.Status.APPROVED}:
            continue
        if candidate.status not in {ProductImageCandidate.Status.QUEUED, ProductImageCandidate.Status.FAILED}:
            continue
        candidate.status = ProductImageCandidate.Status.GENERATING
        candidate.attempt_count += 1
        candidate.last_error_code = ""
        candidate.last_error_message = ""
        candidate.save(
            update_fields=["status", "attempt_count", "last_error_code", "last_error_message", "updated_at"]
        )
        try:
            provider_bytes = generate_image(
                prompt=candidate.prompt,
                seed=candidate.seed,
                reference_image=reference_image if shot_type != ProductImageCandidate.ShotType.HERO else None,
            )
            webp_bytes = prepare_candidate_image(provider_bytes)
            path = draft_path(
                batch_id=generation.batch_id,
                product_slug=generation.source_snapshot["slug"],
                shot_type=shot_type,
                candidate_id=candidate.pk,
                revision=candidate.regeneration_revision,
            )
            public_url = storage.upload(path, webp_bytes)
        except (ImageProviderError, ImageStorageError) as error:
            _mark_failure(generation, candidate, error)
            return True

        candidate.status = ProductImageCandidate.Status.READY
        candidate.storage_path = path
        candidate.public_url = public_url
        candidate.mime_type = "image/webp"
        candidate.width = 768
        candidate.height = 1024
        candidate.save(
            update_fields=[
                "status",
                "storage_path",
                "public_url",
                "mime_type",
                "width",
                "height",
                "updated_at",
            ]
        )
        if shot_type == ProductImageCandidate.ShotType.HERO:
            reference_image = build_reference_image(webp_bytes)

    generation.status = ProductImageGeneration.Status.READY_FOR_REVIEW
    generation.completed_at = timezone.now()
    generation.next_attempt_at = None
    generation.last_error_code = ""
    generation.last_error_message = ""
    generation.save(
        update_fields=[
            "status",
            "completed_at",
            "next_attempt_at",
            "last_error_code",
            "last_error_message",
            "updated_at",
        ]
    )
    recompute_batch(generation.batch_id)
    return True


@transaction.atomic
def approve_candidate(*, candidate_id: object, reviewer) -> ProductImageCandidate:
    candidate = ProductImageCandidate.objects.select_for_update().select_related("generation").get(pk=candidate_id)
    if candidate.status == ProductImageCandidate.Status.APPROVED:
        return candidate
    if candidate.status != ProductImageCandidate.Status.READY:
        raise ImageGenerationWorkflowError("invalid_candidate_state", "Only a ready candidate can be approved.")
    candidate.status = ProductImageCandidate.Status.APPROVED
    candidate.reviewed_by = reviewer
    candidate.reviewed_at = timezone.now()
    candidate.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    generation = candidate.generation
    if not generation.candidates.exclude(status=ProductImageCandidate.Status.APPROVED).exists():
        generation.status = ProductImageGeneration.Status.APPROVED
        generation.save(update_fields=["status", "updated_at"])
    recompute_batch(generation.batch_id)
    return candidate


def reject_candidate(
    *, candidate_id: object, reviewer, storage: SupabaseImageStorage | None = None
) -> ProductImageCandidate:
    candidate = ProductImageCandidate.objects.select_related("generation").get(pk=candidate_id)
    if candidate.status == ProductImageCandidate.Status.REJECTED:
        return candidate
    if candidate.generation.status in {
        ProductImageGeneration.Status.GENERATING,
        ProductImageGeneration.Status.PUBLISHED,
        ProductImageGeneration.Status.CANCELLED,
    }:
        raise ImageGenerationWorkflowError(
            "invalid_candidate_state",
            "This image-generation work cannot be changed.",
        )
    if candidate.status not in {ProductImageCandidate.Status.READY, ProductImageCandidate.Status.APPROVED}:
        raise ImageGenerationWorkflowError("invalid_candidate_state", "Only a generated candidate can be rejected.")
    cleanup_error = None
    if candidate.storage_path:
        try:
            storage = storage or SupabaseImageStorage()
            storage.delete([candidate.storage_path])
        except ImageStorageError as error:
            cleanup_error = error
    with transaction.atomic():
        candidate = ProductImageCandidate.objects.select_for_update().select_related("generation").get(pk=candidate_id)
        candidate.status = ProductImageCandidate.Status.REJECTED
        candidate.reviewed_by = reviewer
        candidate.reviewed_at = timezone.now()
        candidate.last_error_code = "cleanup_needed" if cleanup_error else ""
        candidate.last_error_message = (
            "The rejected draft still needs storage cleanup." if cleanup_error else ""
        )
        if cleanup_error is None:
            candidate.storage_path = ""
            candidate.public_url = ""
        candidate.save()
        generation = candidate.generation
        generation.status = ProductImageGeneration.Status.NEEDS_REGENERATION
        generation.save(update_fields=["status", "updated_at"])
        recompute_batch(generation.batch_id)
    return candidate


def cancel_generation(
    *, generation_id: object, storage: SupabaseImageStorage | None = None
) -> ProductImageGeneration:
    generation = (
        ProductImageGeneration.objects.select_related("product")
        .prefetch_related("candidates")
        .get(pk=generation_id)
    )
    if generation.status == ProductImageGeneration.Status.CANCELLED:
        raise ImageGenerationWorkflowError(
            "already_cancelled",
            "This image-generation work has already been cancelled.",
        )
    if generation.status == ProductImageGeneration.Status.GENERATING:
        raise ImageGenerationWorkflowError(
            "generation_in_progress",
            "Image generation is already in progress. Wait for this worker run to finish before cancelling.",
        )
    if generation.status == ProductImageGeneration.Status.PUBLISHED:
        raise ImageGenerationWorkflowError(
            "already_published",
            "Published generated galleries cannot be removed from the active workspace.",
        )
    allowed_statuses = {
        ProductImageGeneration.Status.QUEUED,
        ProductImageGeneration.Status.READY_FOR_REVIEW,
        ProductImageGeneration.Status.NEEDS_REGENERATION,
        ProductImageGeneration.Status.APPROVED,
        ProductImageGeneration.Status.FAILED,
    }
    if generation.status not in allowed_statuses:
        raise ImageGenerationWorkflowError(
            "invalid_generation_state",
            "This image-generation work cannot be cancelled.",
        )

    candidates = list(generation.candidates.all())
    draft_paths = [
        candidate.storage_path
        for candidate in candidates
        if candidate.storage_path.startswith("ai-drafts/")
    ]
    cleanup_error = None
    if draft_paths:
        try:
            storage = storage or SupabaseImageStorage()
            storage.delete(draft_paths)
        except ImageStorageError as error:
            cleanup_error = error

    batch_id = generation.batch_id
    with transaction.atomic():
        generation = ProductImageGeneration.objects.select_for_update().get(pk=generation_id)
        if generation.status in {
            ProductImageGeneration.Status.CANCELLED,
            ProductImageGeneration.Status.GENERATING,
            ProductImageGeneration.Status.PUBLISHED,
        }:
            raise ImageGenerationWorkflowError(
                "invalid_generation_state",
                "This image-generation work cannot be cancelled.",
            )
        locked_candidates = list(generation.candidates.select_for_update().all())
        deleted_paths = set(draft_paths) if cleanup_error is None else set()
        for candidate in locked_candidates:
            has_draft = candidate.storage_path.startswith("ai-drafts/")
            if candidate.status in {
                ProductImageCandidate.Status.QUEUED,
                ProductImageCandidate.Status.GENERATING,
                ProductImageCandidate.Status.READY,
                ProductImageCandidate.Status.APPROVED,
            }:
                candidate.status = ProductImageCandidate.Status.REJECTED
            if has_draft and candidate.storage_path in deleted_paths:
                candidate.storage_path = ""
                candidate.public_url = ""
            if cleanup_error and has_draft:
                candidate.last_error_code = "cleanup_needed"
                candidate.last_error_message = "The cancelled draft still needs storage cleanup."
            else:
                candidate.last_error_code = ""
                candidate.last_error_message = ""
            candidate.save()
        generation.status = ProductImageGeneration.Status.CANCELLED
        generation.next_attempt_at = None
        generation.completed_at = timezone.now()
        generation.last_error_code = "cleanup_needed" if cleanup_error else ""
        generation.last_error_message = (
            "One or more cancelled drafts still need storage cleanup." if cleanup_error else ""
        )
        generation.save(
            update_fields=[
                "status",
                "next_attempt_at",
                "completed_at",
                "last_error_code",
                "last_error_message",
                "updated_at",
            ]
        )
        batch_id = generation.batch_id
    recompute_batch(batch_id)
    return ProductImageGeneration.objects.select_related("product").prefetch_related("candidates").get(pk=generation_id)


def regenerate_candidate(
    *,
    candidate_id: object,
    scope: str,
    shots: dict[str, dict],
    storage: SupabaseImageStorage | None = None,
) -> ProductImageCandidate:
    candidate = ProductImageCandidate.objects.select_related("generation").get(pk=candidate_id)
    if candidate.generation.status in {
        ProductImageGeneration.Status.PUBLISHED,
        ProductImageGeneration.Status.CANCELLED,
    }:
        raise ImageGenerationWorkflowError(
            "invalid_candidate_state",
            "Published or cancelled image work cannot be regenerated.",
        )
    if candidate.status in {
        ProductImageCandidate.Status.QUEUED,
        ProductImageCandidate.Status.GENERATING,
    }:
        raise ImageGenerationWorkflowError(
            "invalid_candidate_state",
            "A queued or generating candidate cannot be regenerated again.",
        )
    storage = storage or SupabaseImageStorage()
    targets = [candidate]
    if scope == "set":
        targets = list(candidate.generation.candidates.all())
    target_shots = {target.shot_type for target in targets}
    revisions = {
        target.shot_type: target.regeneration_revision + 1 for target in targets
    }
    reserved_colors = {
        other.shot_type: other.manual_overrides.get("resolved", {}).get("color")
        for other in candidate.generation.candidates.all()
        if other.shot_type not in target_shots
        and other.manual_overrides.get("resolved", {}).get("color")
    }
    resolved_overrides = resolve_shot_overrides(
        candidate.generation.source_snapshot,
        shots,
        revisions=revisions,
        reserved_colors=reserved_colors,
    )
    paths = [target.storage_path for target in targets if target.storage_path]
    if paths:
        storage.delete(paths)
    with transaction.atomic():
        locked_targets = list(
            ProductImageCandidate.objects.select_for_update().filter(
                pk__in=[target.pk for target in targets]
            )
        )
        for target in locked_targets:
            target.regeneration_revision += 1
            target.manual_overrides = resolved_overrides[target.shot_type]
            target.prompt_policy_version = PROMPT_POLICY_V2
            target.prompt = build_prompt(
                candidate.generation.source_snapshot,
                target.shot_type,
                target.manual_overrides,
                policy_version=PROMPT_POLICY_V2,
            )
            target.seed = deterministic_seed(
                str(candidate.generation.product_id),
                target.shot_type,
                target.regeneration_revision,
            )
            target.status = ProductImageCandidate.Status.QUEUED
            target.storage_path = ""
            target.public_url = ""
            target.reviewed_by = None
            target.reviewed_at = None
            target.last_error_code = ""
            target.last_error_message = ""
            target.save()
        generation = ProductImageGeneration.objects.select_for_update().get(pk=candidate.generation_id)
        generation.status = ProductImageGeneration.Status.QUEUED
        generation.next_attempt_at = None
        generation.completed_at = None
        generation.last_error_code = ""
        generation.last_error_message = ""
        generation.save()
        recompute_batch(generation.batch_id)
    return ProductImageCandidate.objects.get(pk=candidate_id)


def publish_generation(
    *,
    generation_id: object,
    publication_mode: str,
    storage: SupabaseImageStorage | None = None,
) -> ProductImageGeneration:
    if publication_mode not in ProductImageGeneration.PublicationMode.values:
        raise ImageGenerationWorkflowError(
            "invalid_publication_mode",
            "Choose whether to add the AI images to the gallery or replace the gallery.",
        )
    storage = storage or SupabaseImageStorage()
    copied_paths: list[str] = []
    try:
        with transaction.atomic():
            generation = (
                ProductImageGeneration.objects.select_for_update()
                .select_related("product")
                .get(pk=generation_id)
            )
            if generation.status == ProductImageGeneration.Status.PUBLISHED:
                if generation.publication_mode != publication_mode:
                    raise ImageGenerationWorkflowError(
                        "already_published",
                        "This generated image set has already been published.",
                    )
                return generation
            candidates = {
                candidate.shot_type: candidate
                for candidate in generation.candidates.select_for_update().all()
            }
            if set(candidates) != set(SHOT_ORDER) or any(
                candidates[shot].status != ProductImageCandidate.Status.APPROVED
                for shot in SHOT_ORDER
            ):
                raise ImageGenerationWorkflowError(
                    "incomplete_approval",
                    "Approve hero, alternate, and detail before publishing.",
                )
            product = Product.objects.select_for_update().get(pk=generation.product_id)
            old_images = list(product.images)
            final_urls: list[str] = []
            for shot_type in SHOT_ORDER:
                candidate = candidates[shot_type]
                destination = published_path(
                    generation_id=generation.pk,
                    product_slug=product.slug,
                    shot_type=shot_type,
                )
                final_urls.append(storage.copy(candidate.storage_path, destination))
                copied_paths.append(destination)
                candidate.storage_path = destination
                candidate.public_url = final_urls[-1]
                candidate.save(update_fields=["storage_path", "public_url", "updated_at"])

            generation.previous_images = old_images
            generation.publication_mode = publication_mode
            if publication_mode == ProductImageGeneration.PublicationMode.APPEND:
                resulting_images = [*old_images, *final_urls]
            else:
                resulting_images = final_urls
                removed_images = set(old_images) - set(resulting_images)
                if removed_images:
                    ProductVariant.objects.filter(
                        product=product,
                        image_url__in=removed_images,
                    ).update(image_url="")
            product.images = resulting_images
            product.is_published = True
            product.save(update_fields=["images", "is_published", "updated_at"])
            generation.status = ProductImageGeneration.Status.PUBLISHED
            generation.published_at = timezone.now()
            generation.save(
                update_fields=[
                    "status",
                    "previous_images",
                    "publication_mode",
                    "published_at",
                    "updated_at",
                ]
            )
            transaction.on_commit(lambda: recompute_batch(generation.batch_id))
            return generation
    except Exception:
        if copied_paths:
            try:
                storage.delete(copied_paths)
            except ImageStorageError:
                pass
        raise


@transaction.atomic
def restore_previous_gallery(*, generation_id: object) -> ProductImageGeneration:
    generation = (
        ProductImageGeneration.objects.select_for_update()
        .select_related("product")
        .get(pk=generation_id)
    )
    if generation.status != ProductImageGeneration.Status.PUBLISHED:
        raise ImageGenerationWorkflowError("not_published", "Only a published generated gallery can be restored.")
    product = Product.objects.select_for_update().get(pk=generation.product_id)
    current_images = list(product.images)
    removed_images = set(current_images) - set(generation.previous_images)
    if removed_images:
        ProductVariant.objects.filter(
            product=product,
            image_url__in=removed_images,
        ).update(image_url="")
    product.images = list(generation.previous_images)
    product.save(update_fields=["images", "updated_at"])
    return generation
