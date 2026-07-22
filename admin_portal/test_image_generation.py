import base64
import importlib
import io
from unittest.mock import Mock, patch

import requests
from django.apps import apps
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from admin_portal.image_generation.cloudflare import (
    ImageProviderError,
    build_reference_image,
    generate_image,
    prepare_candidate_image,
)
from admin_portal.image_generation.prompts import (
    PROMPT_POLICY_V2,
    allocate_colors,
    build_prompt,
    representation_profile,
    resolve_shot_overrides,
)
from admin_portal.image_generation.services import (
    ImageGenerationWorkflowError,
    approve_candidate,
    create_batch,
    process_next_generation,
    publish_generation,
    regenerate_candidate,
    reject_candidate,
    restore_previous_gallery,
)
from admin_portal.image_generation.storage import (
    ImageStorageError,
    SupabaseImageStorage,
    draft_path,
    published_path,
)
from admin_portal.models import (
    AdminStaffAccess,
    ImageGenerationBatch,
    ProductImageCandidate,
    ProductImageGeneration,
)
from admin_portal.serializers import ProductImageCandidateSerializer
from catalog.models import Product
from customers.models import CustomerProfile


def image_bytes(size=(768, 1024), image_format="PNG") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color=(210, 190, 160)).save(output, format=image_format)
    return output.getvalue()


def model_shot(**overrides) -> dict:
    return {
        "color": None,
        "bodyProfile": "automatic",
        "skinTone": "automatic",
        "composition": "automatic",
        "instruction": "",
        **overrides,
    }


def detail_shot(**overrides) -> dict:
    return {
        "color": None,
        "detailFocus": "automatic",
        "instruction": "",
        **overrides,
    }


def set_regeneration_payload(**shots) -> dict:
    return {
        "scope": "set",
        "shots": {
            "hero": model_shot(),
            "alternate": model_shot(),
            "detail": detail_shot(),
            **shots,
        },
    }


class FakeStorage:
    def __init__(self):
        self.uploaded: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.copied: list[tuple[str, str]] = []
        self.fail_copy_at: int | None = None

    def upload(self, path: str, content: bytes, *, content_type: str = "image/webp") -> str:
        if path in self.uploaded:
            raise ImageStorageError("storage_collision", "collision")
        self.uploaded[path] = content
        return f"https://project.supabase.co/storage/v1/object/public/product-images/{path}"

    def download(self, path: str) -> bytes:
        return self.uploaded[path]

    def copy(self, source_path: str, destination_path: str) -> str:
        if self.fail_copy_at is not None and len(self.copied) == self.fail_copy_at:
            raise ImageStorageError("storage_copy", "copy failed")
        self.copied.append((source_path, destination_path))
        self.uploaded[destination_path] = self.uploaded[source_path]
        return f"https://project.supabase.co/storage/v1/object/public/product-images/{destination_path}"

    def delete(self, paths: list[str]) -> None:
        self.deleted.extend(paths)
        for path in paths:
            self.uploaded.pop(path, None)


class PromptTests(TestCase):
    def test_prompts_enforce_representation_and_omit_commerce_metadata(self):
        snapshot = {
            "id": "12",
            "slug": "silk-dress",
            "name": "Silk Dress",
            "description": "Bias-cut evening dress",
            "category": "Party & Evening",
            "material": "Silk",
            "tags": ["evening"],
            "colors": ["Gold"],
            "price": 9999,
            "sku": "SECRET-SKU",
            "stock": 20,
            "rating": 5,
            "reviews": 100,
        }
        prompt = build_prompt(snapshot, ProductImageCandidate.ShotType.HERO)

        self.assertIn("adult Black woman", prompt)
        self.assertIn("Never show a white or non-Black model, a man, a child", prompt)
        self.assertIn(representation_profile("12")["identity"], prompt)
        self.assertIn(PROMPT_POLICY_V2, prompt)
        for omitted in ("9999", "SECRET-SKU", "Stock:", "Rating:", "Reviews:"):
            self.assertNotIn(omitted, prompt)

    def test_representation_profile_is_stable_and_varied(self):
        self.assertEqual(representation_profile("abc"), representation_profile("abc"))
        profiles = {
            tuple(representation_profile(str(value)).items()) for value in range(80)
        }
        self.assertEqual(len(profiles), 8)

    def test_hero_and_alternate_are_distinct_and_detail_is_person_free(self):
        snapshot = {
            "id": "42",
            "name": "Dress",
            "description": "A sculpted dress",
            "category": "Dresses",
            "material": "Cotton",
            "tags": [],
            "colors": ["Red", "Black", "Green"],
        }
        overrides = resolve_shot_overrides(snapshot, {
            "hero": {}, "alternate": {}, "detail": {}
        })
        self.assertNotEqual(
            overrides["hero"]["resolved"]["identity"],
            overrides["alternate"]["resolved"]["identity"],
        )
        detail_prompt = build_prompt(snapshot, "detail", overrides["detail"])
        self.assertIn("product-only image", detail_prompt)
        self.assertIn("Show no person, face, hands, limbs", detail_prompt)

    def test_color_allocation_for_three_two_one_and_zero_colors(self):
        for colors, expected_unique in [
            (["Red", "Black", "Green"], 3),
            (["Red", "Black"], 2),
            (["Red"], 1),
            ([], 1),
        ]:
            with self.subTest(colors=colors):
                assignments = allocate_colors(
                    {"id": "stable", "colors": colors},
                    {shot: None for shot in ("hero", "alternate", "detail")},
                )
                self.assertEqual(len(set(assignments.values())), expected_unique)
                self.assertTrue(set(assignments.values()) <= (set(colors) or {None}))

    def test_mixed_explicit_and_automatic_colors_use_remaining_catalog_colors(self):
        assignments = allocate_colors(
            {"id": "stable", "colors": ["Red", "Black", "Green"]},
            {"hero": "Red", "alternate": None, "detail": None},
        )
        self.assertEqual(assignments["hero"], "Red")
        self.assertEqual(set(assignments.values()), {"Red", "Black", "Green"})


@override_settings(
    IMAGE_GENERATION_ENABLED=True,
    CLOUDFLARE_ACCOUNT_ID="account",
    CLOUDFLARE_WORKERS_AI_API_TOKEN="token",
    CLOUDFLARE_IMAGE_MODEL="@cf/black-forest-labs/flux-2-klein-4b",
    CLOUDFLARE_AI_TIMEOUT_SECONDS=1,
)
class CloudflareClientTests(TestCase):
    @patch("admin_portal.image_generation.cloudflare.requests.post")
    def test_success_uses_expected_model_dimensions_and_decodes_image(self, post):
        response = Mock(ok=True)
        response.json.return_value = {
            "success": True,
            "result": {"image": base64.b64encode(image_bytes()).decode("ascii")},
        }
        post.return_value = response

        result = generate_image(prompt="Product", seed=4, reference_image=b"reference")

        self.assertTrue(result)
        call = post.call_args
        self.assertIn("@cf/black-forest-labs/flux-2-klein-4b", call.args[0])
        self.assertEqual(call.kwargs["files"]["width"], (None, "768"))
        self.assertEqual(call.kwargs["files"]["height"], (None, "1024"))
        self.assertEqual(call.kwargs["files"]["input_image_0"][0], "hero-reference.webp")

    @patch("admin_portal.image_generation.cloudflare.requests.post")
    def test_auth_quota_transient_and_malformed_failures_are_classified(self, post):
        cases = [
            (401, {}, "provider_auth", False),
            (429, {"errors": ["daily neuron quota"]}, "daily_quota", True),
            (503, {}, "provider_unavailable", True),
        ]
        for status_code, payload, code, retryable in cases:
            response = Mock(ok=False, status_code=status_code, text="safe")
            response.json.return_value = payload
            post.return_value = response
            with self.subTest(status_code=status_code), self.assertRaises(ImageProviderError) as raised:
                generate_image(prompt="Product", seed=4)
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(raised.exception.retryable, retryable)

        response = Mock(ok=True)
        response.json.return_value = {"result": {"image": "not-base64"}}
        post.return_value = response
        with self.assertRaises(ImageProviderError) as raised:
            generate_image(prompt="Product", seed=4)
        self.assertEqual(raised.exception.code, "malformed_output")

    def test_image_validation_and_reference_dimensions(self):
        webp = prepare_candidate_image(image_bytes())
        reference = build_reference_image(webp)
        with Image.open(io.BytesIO(reference)) as image:
            self.assertLess(image.width, 512)
            self.assertLess(image.height, 512)
        with self.assertRaises(ImageProviderError) as raised:
            prepare_candidate_image(image_bytes((512, 512)))
        self.assertEqual(raised.exception.code, "wrong_dimensions")


@override_settings(
    SUPABASE_URL="https://project.supabase.co",
    SUPABASE_SERVICE_ROLE_KEY="service-key",
    PRODUCT_IMAGES_BUCKET="product-images",
)
class StorageTests(TestCase):
    def test_paths_upload_copy_delete_and_safe_failures(self):
        session = Mock()
        session.post.return_value = Mock(ok=True, status_code=200, text="")
        session.delete.return_value = Mock(ok=True, status_code=200, text="")
        storage = SupabaseImageStorage(session=session)
        draft = draft_path(
            batch_id="batch",
            product_slug="dress",
            shot_type="hero",
            candidate_id="candidate",
            revision=3,
        )
        final = published_path(generation_id="generation", product_slug="dress", shot_type="hero")

        url = storage.upload(draft, b"image")
        final_url = storage.copy(draft, final)
        storage.delete([draft])

        self.assertIn("ai-drafts/batch/dress/hero-candidate-r3.webp", url)
        self.assertIn("products/dress/ai-generated/generation/hero.webp", final_url)
        self.assertEqual(session.post.call_args_list[0].kwargs["headers"]["x-upsert"], "false")
        self.assertNotIn("service-key", str(ImageStorageError("storage_upload", "safe")))


class PublicationModeBackfillTests(TestCase):
    def test_only_historical_published_generations_are_backfilled_as_replace(self):
        owner = CustomerProfile.objects.create(
            supabase_user_id="publication-migration-owner",
            email="publication-migration@test.local",
        )
        products = list(Product.objects.all()[:2])
        batch = ImageGenerationBatch.objects.create(
            model="@cf/black-forest-labs/flux-2-klein-4b",
            product_count=2,
            requested_by=owner,
        )
        published = ProductImageGeneration.objects.create(
            batch=batch,
            product=products[0],
            status=ProductImageGeneration.Status.PUBLISHED,
            model=batch.model,
        )
        unpublished = ProductImageGeneration.objects.create(
            batch=batch,
            product=products[1],
            status=ProductImageGeneration.Status.READY_FOR_REVIEW,
            model=batch.model,
        )
        migration = importlib.import_module(
            "admin_portal.migrations.0004_generation_publication_mode"
        )

        migration.backfill_published_generation_modes(
            apps,
            None,
        )

        published.refresh_from_db()
        unpublished.refresh_from_db()
        self.assertEqual(published.publication_mode, "replace")
        self.assertIsNone(unpublished.publication_mode)


@override_settings(IMAGE_GENERATION_ENABLED=True, CLOUDFLARE_IMAGE_MODEL="@cf/black-forest-labs/flux-2-klein-4b")
class GenerationWorkflowTests(TestCase):
    def setUp(self):
        self.owner = CustomerProfile.objects.create(supabase_user_id="owner-ai", email="owner-ai@test.local")
        self.attendant = CustomerProfile.objects.create(supabase_user_id="attendant-ai", email="attendant-ai@test.local")
        self.customer = CustomerProfile.objects.create(supabase_user_id="customer-ai", email="customer-ai@test.local")
        AdminStaffAccess.objects.create(customer=self.owner, role=AdminStaffAccess.Role.OWNER)
        AdminStaffAccess.objects.create(customer=self.attendant, role=AdminStaffAccess.Role.ATTENDANT)
        self.products = list(Product.objects.select_related("category").all()[:6])
        self.storage = FakeStorage()
        self.client = APIClient()

    def make_batch(self, count=1):
        return create_batch(product_ids=[product.pk for product in self.products[:count]], requested_by=self.owner)

    def generate_ready(self, generation: ProductImageGeneration):
        with patch(
            "admin_portal.image_generation.services.generate_image",
            return_value=image_bytes(),
        ) as provider:
            self.assertTrue(process_next_generation(storage=self.storage))
        self.assertEqual(provider.call_count, 3)
        self.assertIsNone(provider.call_args_list[0].kwargs["reference_image"])
        self.assertIsNotNone(provider.call_args_list[1].kwargs["reference_image"])
        self.assertIsNotNone(provider.call_args_list[2].kwargs["reference_image"])
        generation.refresh_from_db()
        self.assertEqual(generation.status, ProductImageGeneration.Status.READY_FOR_REVIEW)

    def approve_generation(self, generation: ProductImageGeneration):
        self.generate_ready(generation)
        for candidate in generation.candidates.all():
            approve_candidate(candidate_id=candidate.pk, reviewer=self.owner)
        generation.refresh_from_db()
        self.assertEqual(generation.status, ProductImageGeneration.Status.APPROVED)

    def test_owner_can_create_one_to_five_and_invalid_selections_fail(self):
        for count in (1, 5):
            batch = self.make_batch(count)
            self.assertEqual(batch.product_count, count)
            ProductImageGeneration.objects.filter(batch=batch).update(status=ProductImageGeneration.Status.CANCELLED)
        for ids, code in [([], "invalid_batch_size"), ([p.pk for p in self.products], "invalid_batch_size"), ([self.products[0].pk] * 2, "duplicate_products"), ([999999], "unknown_products")]:
            with self.subTest(code=code), self.assertRaises(ImageGenerationWorkflowError) as raised:
                create_batch(product_ids=ids, requested_by=self.owner)
            self.assertEqual(raised.exception.code, code)

    def test_active_product_cannot_be_queued_twice(self):
        self.make_batch()
        with self.assertRaises(ImageGenerationWorkflowError) as raised:
            self.make_batch()
        self.assertEqual(raised.exception.code, "active_generation")

    def test_product_requires_a_colored_variant_before_queueing(self):
        product = self.products[0]
        product.variants.update(color="")

        with self.assertRaises(ImageGenerationWorkflowError) as raised:
            create_batch(product_ids=[product.pk], requested_by=self.owner)

        self.assertEqual(raised.exception.code, "missing_variant_color")
        self.assertFalse(ImageGenerationBatch.objects.exists())

    def test_api_permissions_snapshot_and_admin_draft_visibility(self):
        self.products[0].is_published = False
        self.products[0].save(update_fields=["is_published", "updated_at"])
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/api/v1/admin/image-generations/batches",
            {"productIds": [self.products[0].pk]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        generation = ProductImageGeneration.objects.get(batch_id=response.json()["id"])
        self.assertEqual(generation.source_snapshot["name"], self.products[0].name)
        self.assertNotIn("price", generation.source_snapshot)
        admin_products = self.client.get("/api/v1/admin/products").json()
        self.assertTrue(any(item["adminId"] == str(self.products[0].pk) for item in admin_products))

        for user in (self.attendant, self.customer):
            self.client.force_authenticate(user=user)
            denied = self.client.post(
                "/api/v1/admin/image-generations/batches",
                {"productIds": [self.products[1].pk]},
                format="json",
            )
            self.assertEqual(denied.status_code, 403)

    def test_worker_is_idempotent_and_management_command_respects_limit(self):
        batch = self.make_batch()
        generation = batch.generations.get()
        self.generate_ready(generation)
        self.assertFalse(process_next_generation(storage=self.storage))
        with patch("admin_portal.management.commands.process_product_image_generations.process_next_generation", side_effect=[True, False]) as process:
            call_command("process_product_image_generations", limit=2)
        self.assertEqual(process.call_count, 2)

    def test_transient_failure_is_scheduled_without_losing_other_slots(self):
        batch = self.make_batch()
        generation = batch.generations.get()
        error = ImageProviderError("provider_unavailable", "Temporary provider failure.", retryable=True)
        with patch("admin_portal.image_generation.services.generate_image", side_effect=error):
            process_next_generation(storage=self.storage)
        generation.refresh_from_db()
        hero = generation.candidates.get(shot_type=ProductImageCandidate.ShotType.HERO)
        self.assertEqual(generation.status, ProductImageGeneration.Status.QUEUED)
        self.assertIsNotNone(generation.next_attempt_at)
        self.assertEqual(hero.status, ProductImageCandidate.Status.FAILED)
        self.assertEqual(generation.candidates.exclude(shot_type="hero").filter(status="queued").count(), 2)

    def test_review_regenerate_publish_restore_and_variant_fallback(self):
        batch = self.make_batch()
        generation = batch.generations.get()
        product = generation.product
        old_images = list(product.images)
        variant = product.variants.first()
        variant.image_url = old_images[0]
        variant.save(update_fields=["image_url", "updated_at"])
        self.generate_ready(generation)
        candidates = list(generation.candidates.all())
        detail = generation.candidates.get(shot_type="detail")

        reject_candidate(candidate_id=detail.pk, reviewer=self.owner, storage=self.storage)
        detail.refresh_from_db()
        self.assertEqual(detail.status, ProductImageCandidate.Status.REJECTED)
        regenerate_candidate(
            candidate_id=detail.pk,
            scope="shot",
            shots={"detail": detail_shot()},
            storage=self.storage,
        )
        detail.refresh_from_db()
        self.assertEqual(detail.status, ProductImageCandidate.Status.QUEUED)
        with patch("admin_portal.image_generation.services.generate_image", return_value=image_bytes()):
            process_next_generation(storage=self.storage)

        for candidate in generation.candidates.all():
            approve_candidate(candidate_id=candidate.pk, reviewer=self.owner)
            approve_candidate(candidate_id=candidate.pk, reviewer=self.owner)
        generation.refresh_from_db()
        self.assertEqual(generation.status, ProductImageGeneration.Status.APPROVED)

        publish_generation(
            generation_id=generation.pk,
            publication_mode=ProductImageGeneration.PublicationMode.REPLACE,
            storage=self.storage,
        )
        product.refresh_from_db()
        variant.refresh_from_db()
        self.assertTrue(product.is_published)
        self.assertEqual(len(product.images), 3)
        self.assertEqual(variant.image_url, "")
        self.assertEqual(product.images[0].split("/")[-1], "hero.webp")

        published_images = list(product.images)
        with self.assertRaises(ImageGenerationWorkflowError):
            regenerate_candidate(
                candidate_id=detail.pk,
                scope="shot",
                shots={"detail": detail_shot()},
                storage=self.storage,
            )
        product.refresh_from_db()
        self.assertEqual(product.images, published_images)

        publish_generation(
            generation_id=generation.pk,
            publication_mode=ProductImageGeneration.PublicationMode.REPLACE,
            storage=self.storage,
        )
        product.refresh_from_db()
        self.assertEqual(len(product.images), 3)

        restore_previous_gallery(generation_id=generation.pk)
        product.refresh_from_db()
        self.assertEqual(product.images, old_images)

    def test_failed_publish_keeps_live_gallery_and_cleans_final_copies(self):
        batch = self.make_batch()
        generation = batch.generations.get()
        old_images = list(generation.product.images)
        self.generate_ready(generation)
        for candidate in generation.candidates.all():
            approve_candidate(candidate_id=candidate.pk, reviewer=self.owner)
        self.storage.fail_copy_at = 1

        with self.assertRaises(ImageStorageError):
            publish_generation(
                generation_id=generation.pk,
                publication_mode=ProductImageGeneration.PublicationMode.REPLACE,
                storage=self.storage,
            )

        generation.product.refresh_from_db()
        self.assertEqual(generation.product.images, old_images)
        self.assertTrue(self.storage.deleted)

    def test_database_failure_after_copy_keeps_gallery_and_cleans_every_final_copy(self):
        batch = self.make_batch()
        generation = batch.generations.get()
        old_images = list(generation.product.images)
        self.approve_generation(generation)

        with patch.object(Product, "save", side_effect=RuntimeError("database write failed")):
            with self.assertRaises(RuntimeError):
                publish_generation(
                    generation_id=generation.pk,
                    publication_mode=ProductImageGeneration.PublicationMode.APPEND,
                    storage=self.storage,
                )

        generation.refresh_from_db()
        generation.product.refresh_from_db()
        self.assertEqual(generation.status, ProductImageGeneration.Status.APPROVED)
        self.assertIsNone(generation.publication_mode)
        self.assertEqual(generation.product.images, old_images)
        self.assertEqual(
            set(self.storage.deleted),
            {destination for _source, destination in self.storage.copied},
        )

    def test_append_publication_preserves_galleries_and_variant_assignments(self):
        for image_count in (0, 1, 3, 5):
            with self.subTest(image_count=image_count):
                product = self.products[image_count % len(self.products)]
                ProductImageGeneration.objects.filter(product=product).delete()
                old_images = [f"https://example.com/manual-{index}.webp" for index in range(image_count)]
                product.images = old_images
                product.save(update_fields=["images", "updated_at"])
                variant = product.variants.first()
                variant.image_url = old_images[0] if old_images else ""
                variant.save(update_fields=["image_url", "updated_at"])
                batch = create_batch(product_ids=[product.pk], requested_by=self.owner)
                generation = batch.generations.get()
                self.approve_generation(generation)

                publish_generation(
                    generation_id=generation.pk,
                    publication_mode=ProductImageGeneration.PublicationMode.APPEND,
                    storage=self.storage,
                )

                product.refresh_from_db()
                variant.refresh_from_db()
                generation.refresh_from_db()
                self.assertEqual(product.images[:image_count], old_images)
                self.assertEqual(len(product.images), image_count + 3)
                self.assertEqual(
                    [url.split("/")[-1] for url in product.images[-3:]],
                    ["hero.webp", "alternate.webp", "detail.webp"],
                )
                self.assertEqual(variant.image_url, old_images[0] if old_images else "")
                self.assertEqual(generation.previous_images, old_images)
                self.assertEqual(generation.publication_mode, "append")

                restore_previous_gallery(generation_id=generation.pk)
                product.refresh_from_db()
                variant.refresh_from_db()
                self.assertEqual(product.images, old_images)
                self.assertEqual(variant.image_url, old_images[0] if old_images else "")

    def test_replace_snapshots_gallery_at_publication_and_clears_only_removed_variant_urls(self):
        product = self.products[0]
        queued_images = ["https://example.com/queued.webp"]
        product.images = queued_images
        product.save(update_fields=["images", "updated_at"])
        batch = create_batch(product_ids=[product.pk], requested_by=self.owner)
        generation = batch.generations.get()
        self.assertEqual(generation.previous_images, [])
        self.approve_generation(generation)

        publication_images = [
            "https://example.com/manual-after-queue-1.webp",
            "https://example.com/manual-after-queue-2.webp",
        ]
        product.images = publication_images
        product.save(update_fields=["images", "updated_at"])
        removed_variant, unrelated_variant = list(product.variants.all()[:2])
        removed_variant.image_url = publication_images[0]
        unrelated_variant.image_url = "https://example.com/not-in-gallery.webp"
        removed_variant.save(update_fields=["image_url", "updated_at"])
        unrelated_variant.save(update_fields=["image_url", "updated_at"])

        publish_generation(
            generation_id=generation.pk,
            publication_mode=ProductImageGeneration.PublicationMode.REPLACE,
            storage=self.storage,
        )

        generation.refresh_from_db()
        product.refresh_from_db()
        removed_variant.refresh_from_db()
        unrelated_variant.refresh_from_db()
        self.assertEqual(generation.previous_images, publication_images)
        self.assertEqual(generation.publication_mode, "replace")
        self.assertEqual(len(product.images), 3)
        self.assertEqual(removed_variant.image_url, "")
        self.assertEqual(unrelated_variant.image_url, "https://example.com/not-in-gallery.webp")

        restore_previous_gallery(generation_id=generation.pk)
        product.refresh_from_db()
        self.assertEqual(product.images, publication_images)

    def test_publish_api_requires_an_explicit_publication_mode(self):
        batch = self.make_batch()
        generation = batch.generations.get()
        self.approve_generation(generation)
        self.client.force_authenticate(user=self.owner)
        path = f"/api/v1/admin/image-generations/{generation.pk}/publish"
        original_gallery_count = len(generation.product.images)

        missing = self.client.post(path, {}, format="json")
        invalid = self.client.post(path, {"publicationMode": "merge"}, format="json")
        with patch(
            "admin_portal.image_generation.services.SupabaseImageStorage",
            return_value=self.storage,
        ):
            valid = self.client.post(
                path,
                {"publicationMode": "append"},
                format="json",
            )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["publicationMode"], "append")
        self.assertEqual(
            valid.json()["currentGalleryCount"],
            original_gallery_count + 3,
        )
        generation.refresh_from_db()
        self.assertEqual(generation.publication_mode, "append")

    def test_hero_regeneration_invalidates_dependent_shots(self):
        batch = self.make_batch()
        generation = batch.generations.get()
        self.generate_ready(generation)
        hero = generation.candidates.get(shot_type=ProductImageCandidate.ShotType.HERO)
        regenerate_candidate(
            candidate_id=hero.pk,
            scope="set",
            shots=set_regeneration_payload()["shots"],
            storage=self.storage,
        )
        self.assertFalse(
            generation.candidates.exclude(status=ProductImageCandidate.Status.QUEUED).exists()
        )

    def test_new_batches_store_v2_policy_distinct_colors_and_audit_assignments(self):
        product = self.products[0]
        variants = list(product.variants.all()[:3])
        if len(variants) < 3:
            self.skipTest("Seed catalog needs three variants for this allocation test.")
        for variant, color in zip(variants, ("Red", "Black", "Green"), strict=True):
            variant.color = color
            variant.save(update_fields=["color", "updated_at"])
        batch = create_batch(product_ids=[product.pk], requested_by=self.owner)
        candidates = list(batch.generations.get().candidates.all())
        self.assertTrue(all(item.prompt_policy_version == PROMPT_POLICY_V2 for item in candidates))
        self.assertTrue(all(item.regeneration_revision == 0 for item in candidates))
        self.assertEqual(
            len({item.manual_overrides["resolved"]["color"] for item in candidates}),
            3,
        )

    def test_explicit_regeneration_changes_seed_and_revision_but_retry_does_not(self):
        generation = self.make_batch().generations.get()
        self.generate_ready(generation)
        alternate = generation.candidates.get(shot_type="alternate")
        original_seed = alternate.seed
        original_prompt = alternate.prompt
        regenerate_candidate(
            candidate_id=alternate.pk,
            scope="shot",
            shots={"alternate": model_shot(composition="walking")},
            storage=self.storage,
        )
        alternate.refresh_from_db()
        self.assertEqual(alternate.regeneration_revision, 1)
        self.assertNotEqual(alternate.seed, original_seed)
        self.assertNotEqual(alternate.prompt, original_prompt)
        retry_seed = alternate.seed
        retry_prompt = alternate.prompt
        with patch(
            "admin_portal.image_generation.services.generate_image",
            side_effect=ImageProviderError("provider_unavailable", "Temporary.", retryable=True),
        ):
            process_next_generation(storage=self.storage)
        alternate.refresh_from_db()
        self.assertEqual(alternate.seed, retry_seed)
        self.assertEqual(alternate.prompt, retry_prompt)
        self.assertEqual(alternate.regeneration_revision, 1)

    def test_regeneration_uses_revisioned_storage_and_preview_urls(self):
        generation = self.make_batch().generations.get()
        self.generate_ready(generation)
        alternate = generation.candidates.get(shot_type="alternate")
        initial_path = alternate.storage_path
        initial_preview = ProductImageCandidateSerializer(alternate).data["publicUrl"]

        self.assertTrue(initial_path.endswith("-r0.webp"))
        self.assertTrue(initial_preview.endswith("?v=0"))

        regenerate_candidate(
            candidate_id=alternate.pk,
            scope="shot",
            shots={"alternate": model_shot(composition="seated")},
            storage=self.storage,
        )
        with patch(
            "admin_portal.image_generation.services.generate_image",
            return_value=image_bytes(),
        ):
            process_next_generation(storage=self.storage)
        alternate.refresh_from_db()
        regenerated_preview = ProductImageCandidateSerializer(alternate).data["publicUrl"]

        self.assertNotEqual(alternate.storage_path, initial_path)
        self.assertTrue(alternate.storage_path.endswith("-r1.webp"))
        self.assertTrue(regenerated_preview.endswith("?v=1"))
        self.assertIn(initial_path, self.storage.deleted)

    def test_isolated_regeneration_leaves_other_candidates_unchanged(self):
        generation = self.make_batch().generations.get()
        self.generate_ready(generation)
        before = {
            item.shot_type: (item.status, item.seed, item.public_url)
            for item in generation.candidates.all()
        }
        detail = generation.candidates.get(shot_type="detail")
        regenerate_candidate(
            candidate_id=detail.pk,
            scope="shot",
            shots={"detail": detail_shot(detailFocus="stitching")},
            storage=self.storage,
        )
        after = {item.shot_type: item for item in generation.candidates.all()}
        for shot_type in ("hero", "alternate"):
            self.assertEqual(
                (after[shot_type].status, after[shot_type].seed, after[shot_type].public_url),
                before[shot_type],
            )
        self.assertEqual(after["detail"].status, ProductImageCandidate.Status.QUEUED)

    def test_regeneration_api_validates_scope_colors_enums_and_notes(self):
        product = self.products[0]
        variants = list(product.variants.all()[:3])
        if len(variants) < 3:
            self.skipTest("Seed catalog needs three variants for this validation test.")
        for variant, color in zip(variants, ("Red", "Black", "Green"), strict=True):
            variant.color = color
            variant.save(update_fields=["color", "updated_at"])
        generation = create_batch(product_ids=[product.pk], requested_by=self.owner).generations.get()
        self.generate_ready(generation)
        hero = generation.candidates.get(shot_type="hero")
        self.client.force_authenticate(user=self.owner)

        invalid_payloads = [
            {"scope": "shot", "shots": {"hero": model_shot()}},
            set_regeneration_payload(hero=model_shot(color="Blue")),
            set_regeneration_payload(hero=model_shot(bodyProfile="unsupported")),
            set_regeneration_payload(hero=model_shot(instruction="Use a male model")),
            set_regeneration_payload(hero=model_shot(instruction="Add a new sleeve design")),
            set_regeneration_payload(hero=model_shot(instruction="Make the product blue")),
            set_regeneration_payload(hero=model_shot(instruction="line one\nline two")),
            set_regeneration_payload(hero=model_shot(instruction="x" * 501)),
            set_regeneration_payload(
                hero=model_shot(color="Red"),
                alternate=model_shot(color="Red"),
            ),
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    f"/api/v1/admin/image-generations/candidates/{hero.pk}/regenerate",
                    payload,
                    format="json",
                )
                self.assertEqual(response.status_code, 400)

    def test_regeneration_api_is_owner_only_and_normalizes_manual_direction(self):
        generation = self.make_batch().generations.get()
        self.generate_ready(generation)
        detail = generation.candidates.get(shot_type="detail")
        payload = {
            "scope": "shot",
            "shots": {"detail": detail_shot(instruction="Emphasize   the   seam finish")},
        }
        self.client.force_authenticate(user=self.attendant)
        denied = self.client.post(
            f"/api/v1/admin/image-generations/candidates/{detail.pk}/regenerate",
            payload,
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(user=self.owner)
        with patch(
            "admin_portal.image_generation.services.SupabaseImageStorage",
            return_value=self.storage,
        ):
            response = self.client.post(
                f"/api/v1/admin/image-generations/candidates/{detail.pk}/regenerate",
                payload,
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        detail.refresh_from_db()
        self.assertEqual(
            detail.manual_overrides["requested"]["instruction"],
            "Emphasize the seam finish",
        )

    def test_deleting_product_cancels_queued_generation_and_batch(self):
        batch = self.make_batch()
        product = batch.generations.get().product
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(f"/api/v1/admin/products/{product.pk}")

        self.assertEqual(response.status_code, 204)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ImageGenerationBatch.Status.CANCELLED)
