from django.db import models
from django.utils import timezone

from orders.models import Order


class PaymentTransaction(models.Model):
    class Provider(models.TextChoices):
        SASAPAY = "sasapay", "SasaPay"

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )
    provider = models.CharField(max_length=30, choices=Provider.choices, default=Provider.SASAPAY)
    payment_method = models.CharField(max_length=20, choices=Order.PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED)
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="KES")
    merchant_reference = models.CharField(max_length=80, db_index=True)
    merchant_request_id = models.CharField(max_length=120, blank=True, db_index=True)
    checkout_request_id = models.CharField(max_length=120, blank=True, db_index=True)
    transaction_code = models.CharField(max_length=120, blank=True, db_index=True)
    checkout_url = models.URLField(blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    callback_payload = models.JSONField(default=dict, blank=True)
    last_status_payload = models.JSONField(default=dict, blank=True)
    verification_payload = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.order.order_number} - {self.provider} - {self.status}"


class Receipt(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="receipt",
    )
    payment_transaction = models.ForeignKey(
        "payments.PaymentTransaction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receipts",
    )
    receipt_number = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ISSUED)
    issued_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_to_email = models.EmailField(blank=True)
    total_paid = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="KES")
    payment_method = models.CharField(max_length=20, choices=Order.PaymentMethod.choices)
    payment_reference = models.CharField(max_length=120, blank=True)
    created_by = models.ForeignKey(
        "customers.CustomerProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_receipts",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at", "-id"]

    def __str__(self) -> str:
        return self.receipt_number
