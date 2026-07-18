import math

from rest_framework.exceptions import ValidationError

from catalog.models import ProductVariant
from checkout.models import DeliverySettings, DeliveryZone, PickupLocation


def _normalize_location(value: str | None) -> str:
    return (value or "").strip().lower()


def get_active_pickup_location() -> PickupLocation:
    pickup_location = PickupLocation.objects.filter(is_active=True).first()

    if pickup_location is None:
        raise ValidationError(
            {"detail": "Pickup is not available right now. Please choose delivery instead."}
        )

    return pickup_location


def get_active_delivery_settings() -> DeliverySettings:
    settings = DeliverySettings.objects.filter(is_active=True).first()

    if settings is None:
        raise ValidationError(
            {
                "detail": (
                    "Delivery is not configured right now. "
                    "Please choose pickup while the store updates delivery settings."
                )
            }
        )

    return settings


def _coerce_coordinate(value, *, label: str) -> float:
    if value in (None, ""):
        raise ValidationError(
            {
                "detail": (
                    "Please choose your delivery location from the search suggestions "
                    "so we can calculate the delivery distance."
                )
            }
        )

    try:
        return float(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive branch
        raise ValidationError(
            {
                "detail": (
                    f"The selected {label} is not valid. "
                    "Please choose your location again."
                )
            }
        ) from exc


def _calculate_straight_line_km(
    *,
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> float:
    earth_radius_km = 6371.0
    origin_lat = math.radians(origin_latitude)
    origin_lng = math.radians(origin_longitude)
    destination_lat = math.radians(destination_latitude)
    destination_lng = math.radians(destination_longitude)
    latitude_delta = destination_lat - origin_lat
    longitude_delta = destination_lng - origin_lng

    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(origin_lat) * math.cos(destination_lat) * math.sin(longitude_delta / 2) ** 2
    )
    central_angle = 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))
    return earth_radius_km * central_angle


def _calculate_rider_fee(*, distance_km: float, base_fee: int, increment_per_10km: int) -> int:
    bands = max(1, math.ceil(distance_km / 10))
    return base_fee + max(0, bands - 1) * increment_per_10km


def resolve_delivery_quote_context(*, delivery_details: dict) -> dict[str, object]:
    normalized_county = _normalize_location(delivery_details.get("county"))
    normalized_town = _normalize_location(delivery_details.get("town"))

    if not normalized_county:
        raise ValidationError({"detail": "Please choose a county for delivery."})

    if not normalized_town:
        raise ValidationError({"detail": "Please add your town for delivery."})

    customer_latitude = _coerce_coordinate(
        delivery_details.get("latitude"),
        label="latitude",
    )
    customer_longitude = _coerce_coordinate(
        delivery_details.get("longitude"),
        label="longitude",
    )
    delivery_settings = get_active_delivery_settings()
    distance_km = _calculate_straight_line_km(
        origin_latitude=float(delivery_settings.shop_latitude),
        origin_longitude=float(delivery_settings.shop_longitude),
        destination_latitude=customer_latitude,
        destination_longitude=customer_longitude,
    )
    rider_cutoff_km = min(
        delivery_settings.rider_max_radius_km,
        delivery_settings.parcel_switch_radius_km,
    )

    if distance_km <= rider_cutoff_km:
        delivery_mode = DeliveryZone.DeliveryMode.RIDER
        delivery_fee = _calculate_rider_fee(
            distance_km=distance_km,
            base_fee=delivery_settings.rider_base_fee,
            increment_per_10km=delivery_settings.rider_increment_per_10km,
        )
        return {
            "deliveryMode": delivery_mode,
            "deliveryFee": delivery_fee,
            "manualDeliveryFeeConfirmationRequired": False,
            "allowPayOnDelivery": delivery_settings.allow_pay_on_delivery,
            "estimatedWindow": delivery_settings.rider_estimated_window,
            "distanceKm": round(distance_km, 1),
            "ruleLabel": f"Rider delivery within {rider_cutoff_km} km",
        }

    return {
        "deliveryMode": DeliveryZone.DeliveryMode.PARCEL,
        "deliveryFee": 0,
        "manualDeliveryFeeConfirmationRequired": delivery_settings.parcel_manual_fee_confirmation_required,
        "allowPayOnDelivery": False,
        "estimatedWindow": delivery_settings.parcel_estimated_window,
        "distanceKm": round(distance_km, 1),
        "ruleLabel": f"Parcel delivery beyond {rider_cutoff_km} km",
    }


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
                "productImage": variant.image_url or (variant.product.images[0] if variant.product.images else ""),
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
