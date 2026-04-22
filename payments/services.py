import base64
import json
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib import error, parse, request

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from notifications.services import send_payment_status_notification
from orders.expiry import expire_unpaid_prepay_orders
from orders.models import Order
from payments.models import PaymentTransaction

logger = logging.getLogger(__name__)


@dataclass
class SasaPayConfig:
    base_url: str
    client_id: str
    client_secret: str
    merchant_code: str
    callback_url: str
    timeout_seconds: float


def get_sasapay_config() -> SasaPayConfig:
    config = SasaPayConfig(
        base_url=settings.SASAPAY_BASE_URL.rstrip("/"),
        client_id=settings.SASAPAY_CLIENT_ID,
        client_secret=settings.SASAPAY_CLIENT_SECRET,
        merchant_code=settings.SASAPAY_MERCHANT_CODE,
        callback_url=settings.SASAPAY_CALLBACK_URL,
        timeout_seconds=settings.SASAPAY_TIMEOUT_SECONDS,
    )
    missing_fields = [
        field_name
        for field_name, value in (
            ("SASAPAY_CLIENT_ID", config.client_id),
            ("SASAPAY_CLIENT_SECRET", config.client_secret),
            ("SASAPAY_MERCHANT_CODE", config.merchant_code),
            ("SASAPAY_CALLBACK_URL", config.callback_url),
        )
        if not value
    ]
    if missing_fields:
        raise ValidationError(
            {
                "detail": (
                    "SasaPay is not configured yet. Missing: "
                    + ", ".join(missing_fields)
                )
            }
        )
    return config


def _build_basic_auth_header(client_id: str, client_secret: str) -> str:
    credentials = f"{client_id}:{client_secret}".encode("utf-8")
    return f"Basic {base64.b64encode(credentials).decode('utf-8')}"


def _parse_json_response(response) -> dict:
    payload = response.read().decode("utf-8")
    return json.loads(payload or "{}")


def _request_sasapay(
    *,
    method: str,
    path: str,
    payload: dict | None = None,
    use_basic_auth: bool = False,
    bearer_token: str | None = None,
) -> dict:
    config = get_sasapay_config()
    url = f"{config.base_url}{path}"
    headers = {"Content-Type": "application/json"}

    if use_basic_auth:
        headers["Authorization"] = _build_basic_auth_header(
            config.client_id,
            config.client_secret,
        )
    elif bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    request_body = None
    if payload is not None:
        request_body = json.dumps(payload).encode("utf-8")

    http_request = request.Request(
        url,
        data=request_body,
        headers=headers,
        method=method,
    )

    try:
        with request.urlopen(http_request, timeout=config.timeout_seconds) as response:
            return _parse_json_response(response)
    except error.HTTPError as exc:
        error_payload = _parse_json_response(exc)
        logger.warning("SasaPay request failed: %s %s", path, error_payload)
        raise ValidationError(
            {
                "detail": error_payload.get("detail")
                or error_payload.get("message")
                or "SasaPay rejected the request."
            }
        ) from exc
    except error.URLError as exc:
        logger.exception("Unable to reach SasaPay at %s", path)
        raise ValidationError(
            {"detail": "We could not reach SasaPay right now. Please try again."}
        ) from exc


def generate_sasapay_access_token() -> str:
    response_data = _request_sasapay(
        method="GET",
        path="/api/v1/auth/token/?grant_type=client_credentials",
        use_basic_auth=True,
    )
    access_token = response_data.get("access_token")
    if not access_token:
        raise ValidationError({"detail": "SasaPay did not return an access token."})
    return access_token


def _format_amount(value: int) -> str:
    return f"{Decimal(value):.2f}"


def _get_customer_email(order: Order) -> str:
    if order.customer:
        return order.customer.email
    return order.guest_email


def _normalize_callback_url(url_value: str) -> str:
    parsed = parse.urlparse(url_value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError({"detail": "The provided payment return URL is invalid."})
    return url_value


def get_payment_ready_order(order_number: str) -> Order:
    expire_unpaid_prepay_orders()

    try:
        order = (
            Order.objects.prefetch_related("items", "items__product", "payment_transactions")
            .select_related("customer")
            .get(order_number=order_number)
        )
    except Order.DoesNotExist as exc:
        raise ValidationError({"detail": "We could not find that order."}) from exc

    if order.payment_timing != Order.PaymentTiming.PREPAY:
        raise ValidationError({"detail": "This order does not require online payment."})

    if order.manual_delivery_fee_confirmation_required:
        raise ValidationError(
            {
                "detail": (
                    "Payment will open after the delivery fee is confirmed for this parcel order."
                )
            }
        )

    if order.payment_method != Order.PaymentMethod.MPESA:
        raise ValidationError({"detail": "Only M-Pesa checkout is enabled in this phase."})

    if order.order_status == Order.OrderStatus.CANCELLED:
        raise ValidationError(
            {"detail": "This unpaid order expired and was cancelled. Please start checkout again."}
        )

    return order


def _resolve_existing_checkout_transaction(order: Order) -> PaymentTransaction | None:
    transaction_record = (
        order.payment_transactions.filter(
            provider=PaymentTransaction.Provider.SASAPAY,
            status__in=[
                PaymentTransaction.Status.INITIATED,
                PaymentTransaction.Status.PENDING,
            ],
        )
        .exclude(checkout_url="")
        .first()
    )
    return transaction_record


@transaction.atomic
def create_sasapay_checkout(
    *,
    order_number: str,
    success_url: str,
    failure_url: str,
    redirect_url: str,
) -> PaymentTransaction:
    order = get_payment_ready_order(order_number)

    if order.payment_status == Order.PaymentStatus.PAID:
        raise ValidationError({"detail": "This order has already been paid."})

    existing_transaction = _resolve_existing_checkout_transaction(order)
    if existing_transaction:
        return existing_transaction

    success_url = _normalize_callback_url(success_url)
    failure_url = _normalize_callback_url(failure_url)
    redirect_url = _normalize_callback_url(redirect_url)

    token = generate_sasapay_access_token()
    config = get_sasapay_config()

    request_payload = {
        "MerchantCode": config.merchant_code,
        "Amount": _format_amount(order.total),
        "Reference": order.order_number,
        "Description": f"Payment for order {order.order_number}",
        "Currency": order.currency,
        "PayerEmail": _get_customer_email(order),
        "CallbackUrl": config.callback_url,
        "RedirectUrl": redirect_url,
        "SuccessUrl": success_url,
        "FailureUrl": failure_url,
        "SasaPayWalletEnabled": False,
        "MpesaEnabled": order.payment_method == Order.PaymentMethod.MPESA,
        "CardEnabled": False,
        "AirtelEnabled": False,
    }
    response_data = _request_sasapay(
        method="POST",
        path="/api/v1/payments/card-payments/",
        payload=request_payload,
        bearer_token=token,
    )

    response_code = str(response_data.get("ResponseCode", ""))
    if response_code not in {"0", ""} and not response_data.get("status", False):
        raise ValidationError(
            {
                "detail": response_data.get("ResponseDescription")
                or response_data.get("detail")
                or "SasaPay could not initiate payment for this order."
            }
        )

    transaction_record = PaymentTransaction.objects.create(
        order=order,
        payment_method=order.payment_method,
        status=PaymentTransaction.Status.PENDING,
        amount=order.total,
        currency=order.currency,
        merchant_reference=order.order_number,
        merchant_request_id=str(response_data.get("MerchantRequestID", "")),
        checkout_request_id=str(response_data.get("CheckoutRequestID", "")),
        checkout_url=response_data.get("CheckoutUrl", ""),
        provider_response=response_data,
    )
    return transaction_record


def _parse_amount_to_int(raw_amount: str | int | float | None) -> int | None:
    if raw_amount in (None, ""):
        return None
    try:
        return int(Decimal(str(raw_amount)))
    except (InvalidOperation, ValueError):
        return None


def _is_truthy_payment_flag(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _mark_order_paid(order: Order) -> None:
    order.payment_status = Order.PaymentStatus.PAID
    if order.delivery_mode == Order.DeliveryMode.PICKUP:
        order.order_status = Order.OrderStatus.READY_FOR_PICKUP
    else:
        order.order_status = Order.OrderStatus.PAID
    order.save(update_fields=["payment_status", "order_status", "updated_at"])


def _mark_order_payment_failed(order: Order) -> None:
    order.payment_status = Order.PaymentStatus.FAILED
    order.order_status = Order.OrderStatus.AWAITING_PAYMENT
    order.save(update_fields=["payment_status", "order_status", "updated_at"])


def verify_sasapay_transaction(transaction_code: str) -> dict:
    token = generate_sasapay_access_token()
    config = get_sasapay_config()
    return _request_sasapay(
        method="POST",
        path="/api/v1/transactions/verify/",
        payload={
            "merchantCode": config.merchant_code,
            "transactionCode": transaction_code,
        },
        bearer_token=token,
    )


@transaction.atomic
def process_sasapay_callback(payload: dict) -> PaymentTransaction:
    checkout_request_id = str(payload.get("CheckoutRequestID", ""))
    merchant_request_id = str(payload.get("MerchantRequestID", ""))
    merchant_reference = str(
        payload.get("BillRefNumber")
        or payload.get("MerchantReference")
        or merchant_request_id
    )

    transaction_record = (
        PaymentTransaction.objects.select_for_update()
        .select_related("order")
        .filter(checkout_request_id=checkout_request_id)
        .first()
    )

    if not transaction_record and merchant_request_id:
        transaction_record = (
            PaymentTransaction.objects.select_for_update()
            .select_related("order")
            .filter(merchant_request_id=merchant_request_id)
            .first()
        )

    if not transaction_record and merchant_reference:
        transaction_record = (
            PaymentTransaction.objects.select_for_update()
            .select_related("order")
            .filter(merchant_reference=merchant_reference)
            .first()
        )

    if not transaction_record:
        raise ValidationError({"detail": "No matching payment transaction was found."})

    order = transaction_record.order
    result_code = str(payload.get("ResultCode", ""))
    transaction_record.callback_payload = payload
    transaction_record.checkout_request_id = (
        checkout_request_id or transaction_record.checkout_request_id
    )
    transaction_record.transaction_code = str(
        payload.get("TransactionCode") or transaction_record.transaction_code
    )

    amount_paid = _parse_amount_to_int(payload.get("TransAmount"))
    if amount_paid is not None:
        transaction_record.amount = amount_paid

    previous_payment_status = order.payment_status
    notification_required = False

    if (
        order.order_status == Order.OrderStatus.CANCELLED
        and order.payment_timing == Order.PaymentTiming.PREPAY
    ):
        order.internal_notes = (
            f"{order.internal_notes.rstrip()}\nLate payment callback received after auto-cancellation."
            if order.internal_notes.strip()
            else "Late payment callback received after auto-cancellation."
        )
        order.save(update_fields=["internal_notes", "updated_at"])
        transaction_record.status = PaymentTransaction.Status.FAILED
        transaction_record.failed_at = timezone.now()
        transaction_record.save(
            update_fields=[
                "callback_payload",
                "checkout_request_id",
                "transaction_code",
                "amount",
                "status",
                "failed_at",
                "updated_at",
            ]
        )
        return transaction_record

    if result_code == "0":
        verification_payload = {}
        if transaction_record.transaction_code:
            verification_payload = verify_sasapay_transaction(transaction_record.transaction_code)
        transaction_record.verification_payload = verification_payload
        transaction_record.status = PaymentTransaction.Status.PAID
        transaction_record.paid_at = timezone.now()
        transaction_record.failed_at = None
        _mark_order_paid(order)
        order.payment_expires_at = None
        order.save(update_fields=["payment_expires_at", "updated_at"])
        notification_required = previous_payment_status != Order.PaymentStatus.PAID
    else:
        transaction_record.status = PaymentTransaction.Status.FAILED
        transaction_record.failed_at = timezone.now()
        _mark_order_payment_failed(order)
        notification_required = previous_payment_status != Order.PaymentStatus.FAILED

    transaction_record.save(
        update_fields=[
            "callback_payload",
            "checkout_request_id",
            "transaction_code",
            "amount",
            "verification_payload",
            "status",
            "paid_at",
            "failed_at",
            "updated_at",
        ]
    )

    if notification_required:
        transaction.on_commit(lambda: send_payment_status_notification(order.pk))

    return transaction_record


@transaction.atomic
def sync_sasapay_status(*, order_number: str) -> PaymentTransaction:
    order = get_payment_ready_order(order_number)
    transaction_record = order.payment_transactions.filter(
        provider=PaymentTransaction.Provider.SASAPAY,
    ).first()
    if not transaction_record:
        raise ValidationError({"detail": "No SasaPay payment has been started for this order."})

    token = generate_sasapay_access_token()
    config = get_sasapay_config()
    status_payload = _request_sasapay(
        method="POST",
        path="/api/v1/transactions/status-query/",
        payload={
            "MerchantCode": config.merchant_code,
            "CheckoutRequestId": transaction_record.checkout_request_id,
            "MerchantTransactionReference": transaction_record.merchant_reference,
            "TransactionCode": transaction_record.transaction_code,
            "CallbackUrl": config.callback_url,
        },
        bearer_token=token,
    )

    transaction_record.last_status_payload = status_payload
    transaction_record.last_synced_at = timezone.now()
    transaction_record.save(update_fields=["last_status_payload", "last_synced_at", "updated_at"])

    paid = _is_truthy_payment_flag(status_payload.get("Paid"))
    if paid is True:
        process_sasapay_callback(
            {
                "CheckoutRequestID": transaction_record.checkout_request_id,
                "MerchantRequestID": transaction_record.merchant_request_id,
                "BillRefNumber": transaction_record.merchant_reference,
                "ResultCode": "0",
                "ResultDesc": status_payload.get("ResultDescription", "Transaction completed successfully"),
                "TransactionCode": status_payload.get("TransactionCode")
                or status_payload.get("TransID", ""),
                "TransAmount": status_payload.get("PaidAmount")
                or status_payload.get("RequestedAmount"),
                "TransactionDate": status_payload.get("PaidDate", ""),
            }
        )
        transaction_record.refresh_from_db()
    else:
        transaction_record.status = PaymentTransaction.Status.PENDING
        transaction_record.save(update_fields=["status", "updated_at"])

    return transaction_record
