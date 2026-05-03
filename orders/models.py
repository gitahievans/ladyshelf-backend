from django.db import models


class Order(models.Model):
    class Currency(models.TextChoices):
        KES = "KES", "KES"

    class PaymentMethod(models.TextChoices):
        MPESA = "mpesa", "M-Pesa"
        CARD = "card", "Card"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        MANUAL_ON_DELIVERY = "manual_on_delivery", "Manual on Delivery"
        REFUNDED = "refunded", "Refunded"

    class PaymentTiming(models.TextChoices):
        PREPAY = "prepay", "Prepay"
        PAY_ON_DELIVERY = "pay_on_delivery", "Pay on Delivery"

    class DeliveryMode(models.TextChoices):
        RIDER = "rider", "Rider"
        PARCEL = "parcel", "Parcel"
        PICKUP = "pickup", "Pickup"

    class OrderStatus(models.TextChoices):
        NEW = "new", "New"
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting Payment"
        PAID = "paid", "Paid"
        AWAITING_DELIVERY_FEE_CONFIRMATION = (
            "awaiting_delivery_fee_confirmation",
            "Awaiting Delivery Fee Confirmation",
        )
        READY_FOR_DISPATCH = "ready_for_dispatch", "Ready for Dispatch"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        READY_FOR_PICKUP = "ready_for_pickup", "Ready for Pickup"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(
        "customers.CustomerProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    guest_email = models.EmailField(blank=True)
    order_number = models.CharField(max_length=40, unique=True)
    delivery_details = models.JSONField(default=dict)
    subtotal = models.PositiveIntegerField()
    delivery_fee = models.PositiveIntegerField(default=0)
    discount = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField()
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.KES,
    )
    delivery_mode = models.CharField(max_length=20, choices=DeliveryMode.choices, blank=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    payment_timing = models.CharField(
        max_length=20,
        choices=PaymentTiming.choices,
        default=PaymentTiming.PREPAY,
    )
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices)
    order_status = models.CharField(max_length=40, choices=OrderStatus.choices)
    manual_delivery_fee_confirmation_required = models.BooleanField(default=False)
    payment_expires_at = models.DateTimeField(null=True, blank=True)
    pickup_instructions = models.JSONField(null=True, blank=True, default=None)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "catalog.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_items",
    )
    variant_id = models.CharField(max_length=50)
    quantity = models.PositiveIntegerField(default=1)
    cancelled_quantity = models.PositiveIntegerField(default=0)
    product_name = models.CharField(max_length=255)
    product_image = models.URLField()
    price = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, choices=Order.Currency.choices, default=Order.Currency.KES)
    size = models.CharField(max_length=20)
    color = models.CharField(max_length=120)
    color_hex = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.order.order_number} - {self.product_name}"


class OrderCancellation(models.Model):
    class Reason(models.TextChoices):
        ORDERED_BY_MISTAKE = "ordered_by_mistake", "Ordered by mistake"
        CHANGED_MIND = "changed_mind", "Changed my mind"
        WRONG_SIZE_OR_COLOR = "wrong_size_or_color", "Need a different size or color"
        DELIVERY_TIMING = "delivery_timing", "Delivery timing no longer works"
        FOUND_ANOTHER_OPTION = "found_another_option", "Found another option"
        OTHER = "other", "Other"

    class Source(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        STAFF = "staff", "Staff"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="cancellations",
    )
    customer = models.ForeignKey(
        "customers.CustomerProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_cancellations",
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.CUSTOMER)
    reason = models.CharField(max_length=40, choices=Reason.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.order.order_number} cancellation"


class OrderCancellationItem(models.Model):
    cancellation = models.ForeignKey(
        OrderCancellation,
        on_delete=models.CASCADE,
        related_name="items",
    )
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="cancellation_items",
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveIntegerField()
    line_total = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.order_item.product_name} x{self.quantity}"
