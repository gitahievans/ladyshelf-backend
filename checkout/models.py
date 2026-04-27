from django.db import models


class DeliverySettings(models.Model):
    name = models.CharField(max_length=120, default="Primary Delivery Settings")
    shop_name = models.CharField(max_length=120, default="Wahi Fashion Roysambu")
    shop_county = models.CharField(max_length=120, default="Nairobi")
    shop_town = models.CharField(max_length=120, default="Roysambu")
    shop_street_address = models.CharField(max_length=255, default="Lumumba Drive, Roysambu")
    shop_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    shop_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    rider_max_radius_km = models.PositiveIntegerField(default=50)
    parcel_switch_radius_km = models.PositiveIntegerField(default=50)
    rider_base_fee = models.PositiveIntegerField(default=200)
    rider_increment_per_10km = models.PositiveIntegerField(default=200)
    rider_estimated_window = models.CharField(max_length=120, default="2-3 business days")
    parcel_estimated_window = models.CharField(max_length=120, default="Dispatch arranged after payment confirmation")
    allow_pay_on_delivery = models.BooleanField(default=True)
    parcel_manual_fee_confirmation_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


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
