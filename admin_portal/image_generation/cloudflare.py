import base64
import binascii
import io

import requests
from django.conf import settings
from PIL import Image, UnidentifiedImageError


EXPECTED_WIDTH = 768
EXPECTED_HEIGHT = 1024
MAX_PROVIDER_BYTES = 20 * 1024 * 1024
MAX_CANDIDATE_BYTES = 8 * 1024 * 1024


class ImageProviderError(Exception):
    def __init__(self, code: str, safe_message: str, *, retryable: bool = False):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable


def _classify_error(response: requests.Response) -> ImageProviderError:
    status_code = response.status_code
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error_text = str(payload.get("errors", "")).lower() if isinstance(payload, dict) else ""

    if status_code in {401, 403}:
        return ImageProviderError("provider_auth", "Cloudflare image generation credentials are invalid.")
    if status_code == 429:
        is_quota = "quota" in error_text or "daily" in error_text or "neuron" in error_text
        return ImageProviderError(
            "daily_quota" if is_quota else "provider_rate_limit",
            "The daily image-generation quota is exhausted." if is_quota else "Image generation is temporarily rate limited.",
            retryable=True,
        )
    if "moderation" in error_text or "unsafe" in error_text or "safety" in error_text:
        return ImageProviderError("moderation", "Cloudflare rejected this candidate under its safety policy.")
    if status_code in {400, 404, 422}:
        return ImageProviderError("provider_configuration", "The configured image model or request is invalid.")
    if status_code >= 500:
        return ImageProviderError("provider_unavailable", "Cloudflare image generation is temporarily unavailable.", retryable=True)
    return ImageProviderError("provider_error", "Cloudflare could not generate this image.")


def _extract_image(payload: object) -> bytes:
    if not isinstance(payload, dict):
        raise ImageProviderError("malformed_output", "Cloudflare returned an unreadable image response.")
    result = payload.get("result", payload)
    image_value = result.get("image") if isinstance(result, dict) else None
    if not isinstance(image_value, str) or not image_value:
        raise ImageProviderError("malformed_output", "Cloudflare returned no usable image.")
    try:
        image_bytes = base64.b64decode(image_value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageProviderError("malformed_output", "Cloudflare returned invalid image data.") from exc
    if not image_bytes or len(image_bytes) > MAX_PROVIDER_BYTES:
        raise ImageProviderError("malformed_output", "Cloudflare returned an invalid image size.")
    return image_bytes


def generate_image(*, prompt: str, seed: int, reference_image: bytes | None = None) -> bytes:
    if not settings.IMAGE_GENERATION_ENABLED:
        raise ImageProviderError("generation_disabled", "Image generation is currently disabled.")
    if not settings.CLOUDFLARE_ACCOUNT_ID or not settings.CLOUDFLARE_WORKERS_AI_API_TOKEN:
        raise ImageProviderError("provider_configuration", "Cloudflare image generation is not configured.")

    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.CLOUDFLARE_ACCOUNT_ID}/ai/run/{settings.CLOUDFLARE_IMAGE_MODEL}"
    )
    multipart = {
        "prompt": (None, prompt),
        "seed": (None, str(seed)),
        "width": (None, str(EXPECTED_WIDTH)),
        "height": (None, str(EXPECTED_HEIGHT)),
    }
    if reference_image is not None:
        multipart["input_image_0"] = ("hero-reference.webp", reference_image, "image/webp")

    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {settings.CLOUDFLARE_WORKERS_AI_API_TOKEN}"},
            files=multipart,
            timeout=settings.CLOUDFLARE_AI_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise ImageProviderError("provider_timeout", "Cloudflare image generation timed out.", retryable=True) from exc
    except requests.RequestException as exc:
        raise ImageProviderError("provider_unavailable", "Cloudflare image generation is temporarily unavailable.", retryable=True) from exc

    if not response.ok:
        raise _classify_error(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise ImageProviderError("malformed_output", "Cloudflare returned an unreadable image response.") from exc
    return _extract_image(payload)


def prepare_candidate_image(image_bytes: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            if image.size != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
                raise ImageProviderError(
                    "wrong_dimensions",
                    f"Generated image dimensions must be {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}.",
                )
            converted = image.convert("RGB")
            output = io.BytesIO()
            converted.save(output, format="WEBP", quality=88, method=6)
    except ImageProviderError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageProviderError("invalid_image", "Cloudflare returned an invalid image file.") from exc
    result = output.getvalue()
    if not result or len(result) > MAX_CANDIDATE_BYTES:
        raise ImageProviderError("invalid_image", "The generated image is too large to store safely.")
    return result


def build_reference_image(image_bytes: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            converted = image.convert("RGB")
            converted.thumbnail((383, 511), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            converted.save(output, format="WEBP", quality=78, method=6)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageProviderError("invalid_reference", "The hero reference image could not be prepared.") from exc
