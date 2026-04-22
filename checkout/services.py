from collections.abc import Iterable

from rest_framework.exceptions import ValidationError

from catalog.models import ProductVariant
from checkout.models import DeliveryZone, PickupLocation


def _normalize_location(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalize_many(values: Iterable[str]) -> set[str]:
    return {_normalize_location(value) for value in values if value}


def get_active_pickup_location() -> PickupLocation:
    pickup_location = PickupLocation.objects.filter(is_active=True).first()

    if pickup_location is None:
        raise ValidationError(
            {"detail": "Pickup is not available right now. Please choose delivery instead."}
        )

    return pickup_location


def resolve_delivery_zone(county: str, town: str) -> DeliveryZone:
    normalized_county = _normalize_location(county)
    normalized_town = _normalize_location(town)

    if not normalized_county:
        raise ValidationError({"detail": "Please choose a county for delivery."})

    if not normalized_town:
        raise ValidationError({"detail": "Please add your town for delivery."})

    zones = DeliveryZone.objects.filter(is_active=True).order_by("priority", "id")

    rider_match: DeliveryZone | None = None
    parcel_match: DeliveryZone | None = None

    for zone in zones:
        zone_counties = _normalize_many(zone.counties)
        zone_towns = _normalize_many(zone.towns)

        if zone_counties and normalized_county not in zone_counties:
            continue

        if zone_towns and normalized_town not in zone_towns:
            continue

        if zone.delivery_mode == DeliveryZone.DeliveryMode.RIDER and rider_match is None:
            rider_match = zone

        if zone.delivery_mode == DeliveryZone.DeliveryMode.PARCEL and parcel_match is None:
            parcel_match = zone

    if rider_match is not None:
        return rider_match

    if parcel_match is not None:
        return parcel_match

    raise ValidationError(
        {
            "detail": (
                "We do not have a delivery rule for that location yet. "
                "Please confirm the town and county or choose pickup."
            )
        }
    )


def build_validated_cart_items(
    cart_lines: list[dict],
    *,
    lock_variants: bool = False,
) -> tuple[list[dict], int]:
    variant_ids = [line["variantId"] for line in cart_lines]
    queryset = ProductVariant.objects.select_related("product", "product__category")
    if lock_variants:
        queryset = queryset.select_for_update()

    variants = {variant.external_id: variant for variant in queryset.filter(external_id__in=variant_ids)}

    items: list[dict] = []
    subtotal = 0

    for line in cart_lines:
        variant = variants.get(line["variantId"])

        if variant is None:
            raise ValidationError(
                {"detail": f"One of the selected pieces is no longer available."}
            )

        if variant.product.external_id != line["productId"]:
            raise ValidationError(
                {"detail": f"The selected size or color no longer matches that product."}
            )

        quantity = line["quantity"]

        if variant.stock < quantity:
            raise ValidationError(
                {
                    "detail": (
                        f"Only {variant.stock} piece(s) remain for "
                        f"{variant.product.name} in {variant.color} / {variant.size}."
                    )
                }
            )

        line_total = variant.product.price * quantity
        subtotal += line_total
        items.append(
            {
                "id": variant.external_id,
                "productId": variant.product.external_id,
                "variantId": variant.external_id,
                "quantity": quantity,
                "productName": variant.product.name,
                "productImage": variant.product.images[0] if variant.product.images else "",
                "price": variant.product.price,
                "currency": variant.product.currency,
                "size": variant.size,
                "color": variant.color,
                "colorHex": variant.color_hex,
                "lineTotal": line_total,
                "availableStock": variant.stock,
            }
        )

    return items, subtotal


def build_payment_options(
    delivery_mode: str,
    allow_pay_on_delivery: bool,
) -> list[dict[str, str]]:
    options = [
        {
            "key": "mpesa-prepay",
            "method": "mpesa",
            "timing": "prepay",
            "label": "Pay with M-Pesa",
            "description": "Confirm an M-Pesa prompt before we prepare your order.",
        },
    ]

    if delivery_mode == "rider" and allow_pay_on_delivery:
        options.append(
            {
                "key": "mpesa-pay-on-delivery",
                "method": "mpesa",
                "timing": "pay_on_delivery",
                "label": "Pay on Delivery with M-Pesa",
                "description": "Available only for rider-served addresses.",
            }
        )

    return options


def validate_payment_selection(
    payment_selection: dict | None,
    available_options: list[dict[str, str]],
) -> dict | None:
    if payment_selection is None:
        return None

    for option in available_options:
        if (
            option["method"] == payment_selection["method"]
            and option["timing"] == payment_selection["timing"]
        ):
            return payment_selection

    raise ValidationError(
        {
            "detail": (
                "That payment option is not available for the selected delivery or pickup choice."
            )
        }
    )
