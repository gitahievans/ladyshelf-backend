from django.db import models


class DeliveryZone(models.Model):
    class DeliveryMode(models.TextChoices):
        RIDER = "rider", "Rider"
        PARCEL = "parcel", "Parcel"

    name = models.CharField(max_length=120)
    delivery_mode = models.CharField(max_length=20, choices=DeliveryMode.choices)
    counties = models.JSONField(default=list, blank=True)
    towns = models.JSONField(default=list, blank=True)
    delivery_fee = models.PositiveIntegerField(default=0)
    manual_fee_confirmation_required = models.BooleanField(default=False)
    allow_pay_on_delivery = models.BooleanField(default=False)
    estimated_window = models.CharField(max_length=120, blank=True)
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self) -> str:
        return self.name


class PickupLocation(models.Model):
    name = models.CharField(max_length=120)
    county = models.CharField(max_length=120)
    town = models.CharField(max_length=120)
    street_address = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=120, blank=True)
    contact_phone = models.CharField(max_length=30)
    maps_url = models.URLField()
    opening_hours = models.CharField(max_length=120, blank=True)
    collection_window_hours = models.PositiveIntegerField(default=72)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
