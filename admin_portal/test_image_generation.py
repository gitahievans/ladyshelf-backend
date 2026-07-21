import base64
import io
from unittest.mock import Mock, patch

import requests
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
from admin_portal.image_generation.prompts import build_prompt, representation_profile
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
from catalog.models import Product
from customers.models import CustomerProfile


def image_bytes(size=(768, 1024), image_format="PNG") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, color=(210, 190, 160)).save(output, format=image_format)
    return output.getvalue()


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
        self.assertIn("No white models, no men, no children", prompt)
        self.assertIn(representation_profile("12"), prompt)
        for omitted in ("9999", "SECRET-SKU", "Stock:", "Rating:", "Reviews:"):
            self.assertNotIn(omitted, prompt)

    def test_representation_profile_is_stable_and_varied(self):
        self.assertEqual(representation_profile("abc"), representation_profile("abc"))
        profiles = {representation_profile(str(value)) for value in range(40)}
        self.assertEqual(len(profiles), 4)


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
        draft = draft_path(batch_id="batch", product_slug="dress", shot_type="hero", candidate_id="candidate")
        final = published_path(generation_id="generation", product_slug="dress", shot_type="hero")

        url = storage.upload(draft, b"image")
        final_url = storage.copy(draft, final)
        storage.delete([draft])

        self.assertIn("ai-drafts/batch/dress/hero-candidate.webp", url)
        self.assertIn("products/dress/ai-generated/generation/hero.webp", final_url)
        self.assertEqual(session.post.call_args_list[0].kwargs["headers"]["x-upsert"], "false")
        self.assertNotIn("service-key", str(ImageStorageError("storage_upload", "safe")))


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

        reject_candidate(candidate_id=candidates[2].pk, reviewer=self.owner, storage=self.storage)
        candidates[2].refresh_from_db()
        self.assertEqual(candidates[2].status, ProductImageCandidate.Status.REJECTED)
        regenerate_candidate(candidate_id=candidates[2].pk, storage=self.storage)
        candidates[2].refresh_from_db()
        self.assertEqual(candidates[2].status, ProductImageCandidate.Status.QUEUED)
        with patch("admin_portal.image_generation.services.generate_image", return_value=image_bytes()):
            process_next_generation(storage=self.storage)

        for candidate in generation.candidates.all():
            approve_candidate(candidate_id=candidate.pk, reviewer=self.owner)
            approve_candidate(candidate_id=candidate.pk, reviewer=self.owner)
        generation.refresh_from_db()
        self.assertEqual(generation.status, ProductImageGeneration.Status.APPROVED)

        publish_generation(generation_id=generation.pk, storage=self.storage)
        product.refresh_from_db()
        variant.refresh_from_db()
        self.assertTrue(product.is_published)
        self.assertEqual(len(product.images), 3)
        self.assertEqual(variant.image_url, "")
        self.assertEqual(product.images[0].split("/")[-1], "hero.webp")

        publish_generation(generation_id=generation.pk, storage=self.storage)
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
            publish_generation(generation_id=generation.pk, storage=self.storage)

        generation.product.refresh_from_db()
        self.assertEqual(generation.product.images, old_images)
        self.assertTrue(self.storage.deleted)

    def test_hero_regeneration_invalidates_dependent_shots(self):
        batch = self.make_batch()
        generation = batch.generations.get()
        self.generate_ready(generation)
        hero = generation.candidates.get(shot_type=ProductImageCandidate.ShotType.HERO)
        regenerate_candidate(candidate_id=hero.pk, storage=self.storage)
        self.assertFalse(
            generation.candidates.exclude(status=ProductImageCandidate.Status.QUEUED).exists()
        )

    def test_deleting_product_cancels_queued_generation_and_batch(self):
        batch = self.make_batch()
        product = batch.generations.get().product
        self.client.force_authenticate(user=self.owner)

        response = self.client.delete(f"/api/v1/admin/products/{product.pk}")

        self.assertEqual(response.status_code, 204)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ImageGenerationBatch.Status.CANCELLED)
