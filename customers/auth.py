from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import jwt
from django.conf import settings
from django.utils.dateparse import parse_datetime
from rest_framework import authentication, exceptions

from customers.models import CustomerProfile


@dataclass
class SupabaseClaims:
    email: str
    email_confirmed_at: datetime | None
    first_name: str
    last_name: str
    phone: str
    avatar_url: str
    sub: str


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""

    return parts[0], " ".join(parts[1:])


def _extract_claims(payload: dict[str, Any]) -> SupabaseClaims:
    user_metadata = payload.get("user_metadata") or payload.get("app_metadata") or {}
    first_name = user_metadata.get("first_name", "")
    last_name = user_metadata.get("last_name", "")

    if not first_name and not last_name:
        first_name, last_name = _split_name(
            user_metadata.get("full_name") or user_metadata.get("name") or ""
        )

    return SupabaseClaims(
        email=payload.get("email", ""),
        email_confirmed_at=parse_datetime(payload.get("email_confirmed_at") or "") if payload.get("email_confirmed_at") else None,
        first_name=first_name,
        last_name=last_name,
        phone=user_metadata.get("phone", "") or payload.get("phone", "") or "",
        avatar_url=user_metadata.get("avatar_url", "") or "",
        sub=payload["sub"],
    )


class SupabaseJWTAuthentication(authentication.BaseAuthentication):
    _jwk_client: jwt.PyJWKClient | None = None

    def authenticate(self, request):
        authorization = authentication.get_authorization_header(request).decode("utf-8")
        if not authorization:
            return None

        parts = authorization.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise exceptions.AuthenticationFailed("Invalid authorization header.")

        token = parts[1]
        payload = self._decode_token(token)
        customer = self._get_or_create_customer(payload)

        return customer, payload

    def _decode_token(self, token: str) -> dict[str, Any]:
        if not settings.SUPABASE_JWKS_URL or not settings.SUPABASE_ISSUER:
            raise exceptions.AuthenticationFailed("Supabase authentication is not configured.")

        try:
            signing_key = self._get_jwk_client().get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                issuer=settings.SUPABASE_ISSUER,
                options={"verify_aud": False},
            )
        except jwt.InvalidTokenError as exc:
            raise exceptions.AuthenticationFailed("Invalid Supabase access token.") from exc

    def _get_jwk_client(self) -> jwt.PyJWKClient:
        if self.__class__._jwk_client is None:
            self.__class__._jwk_client = jwt.PyJWKClient(settings.SUPABASE_JWKS_URL)
        return self.__class__._jwk_client

    def _get_or_create_customer(self, payload: dict[str, Any]) -> CustomerProfile:
        claims = _extract_claims(payload)
        defaults = {
            "email": claims.email,
            "email_confirmed_at": claims.email_confirmed_at,
            "first_name": claims.first_name,
            "last_name": claims.last_name,
            "phone": claims.phone,
            "avatar_url": claims.avatar_url,
        }
        customer, _ = CustomerProfile.objects.get_or_create(
            supabase_user_id=claims.sub,
            defaults=defaults,
        )

        updates = []
        synced_fields = {
            "email": claims.email,
            "email_confirmed_at": claims.email_confirmed_at,
            "avatar_url": claims.avatar_url,
        }
        backfill_fields = {
            "first_name": claims.first_name,
            "last_name": claims.last_name,
            "phone": claims.phone,
        }

        for field, value in synced_fields.items():
            if value and getattr(customer, field) != value:
                setattr(customer, field, value)
                updates.append(field)

        for field, value in backfill_fields.items():
            if value and not getattr(customer, field):
                setattr(customer, field, value)
                updates.append(field)

        if updates:
            customer.save(update_fields=[*updates, "updated_at"])

        return customer
