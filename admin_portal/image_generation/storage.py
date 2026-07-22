from urllib.parse import quote

import requests
from django.conf import settings


class ImageStorageError(Exception):
    def __init__(self, code: str, safe_message: str):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class SupabaseImageStorage:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.base_url = settings.SUPABASE_URL.rstrip("/")
        self.bucket = settings.PRODUCT_IMAGES_BUCKET
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY
        if not self.base_url or not self.service_key:
            raise ImageStorageError("storage_configuration", "Product image storage is not configured.")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }

    def public_url(self, path: str) -> str:
        return (
            f"{self.base_url}/storage/v1/object/public/"
            f"{quote(self.bucket, safe='')}/{quote(path, safe='/')}"
        )

    def upload(self, path: str, content: bytes, *, content_type: str = "image/webp") -> str:
        response = self.session.post(
            f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}/{quote(path, safe='/')}",
            headers={**self.headers, "Content-Type": content_type, "x-upsert": "false"},
            data=content,
            timeout=30,
        )
        if response.status_code == 409 or (
            response.status_code == 400 and "already" in response.text.lower()
        ):
            raise ImageStorageError("storage_collision", "A product image already exists at the generated path.")
        if not response.ok:
            raise ImageStorageError("storage_upload", "The generated image could not be stored.")
        return self.public_url(path)

    def download(self, path: str) -> bytes:
        response = self.session.get(
            f"{self.base_url}/storage/v1/object/authenticated/{quote(self.bucket, safe='')}/{quote(path, safe='/')}",
            headers=self.headers,
            timeout=30,
        )
        if not response.ok:
            raise ImageStorageError("storage_download", "The generated image could not be read from storage.")
        return response.content

    def copy(self, source_path: str, destination_path: str) -> str:
        response = self.session.post(
            f"{self.base_url}/storage/v1/object/copy",
            headers={**self.headers, "Content-Type": "application/json", "x-upsert": "false"},
            json={
                "bucketId": self.bucket,
                "sourceKey": source_path,
                "destinationBucket": self.bucket,
                "destinationKey": destination_path,
            },
            timeout=30,
        )
        if not response.ok:
            raise ImageStorageError("storage_copy", "The approved image set could not be prepared for publication.")
        return self.public_url(destination_path)

    def delete(self, paths: list[str]) -> None:
        if not paths:
            return
        response = self.session.delete(
            f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}",
            headers={**self.headers, "Content-Type": "application/json"},
            json={"prefixes": paths},
            timeout=30,
        )
        if not response.ok:
            raise ImageStorageError("storage_delete", "The generated image could not be removed from storage.")


def draft_path(
    *,
    batch_id: object,
    product_slug: str,
    shot_type: str,
    candidate_id: object,
    revision: int,
) -> str:
    return (
        f"ai-drafts/{batch_id}/{product_slug}/"
        f"{shot_type}-{candidate_id}-r{revision}.webp"
    )


def published_path(*, generation_id: object, product_slug: str, shot_type: str) -> str:
    return f"products/{product_slug}/ai-generated/{generation_id}/{shot_type}.webp"
