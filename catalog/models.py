from django.db import models


class Category(models.Model):
    external_id = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    image = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    class Currency(models.TextChoices):
        KES = "KES", "KES"

    class Badge(models.TextChoices):
        NEW = "new", "New"
        SALE = "sale", "Sale"
        BESTSELLER = "bestseller", "Bestseller"
        LIMITED = "limited", "Limited"

    external_id = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=120, default="Wahi Fashion")
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
    )
    description = models.TextField()
    images = models.JSONField(default=list)
    price = models.PositiveIntegerField()
    original_price = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.KES,
    )
    badge = models.CharField(
        max_length=20,
        choices=Badge.choices,
        null=True,
        blank=True,
    )
    tags = models.JSONField(default=list)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    material = models.TextField(blank=True)
    care_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "name"]

    def __str__(self) -> str:
        return self.name


class ProductVariant(models.Model):
    external_id = models.CharField(max_length=50, unique=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )
    size = models.CharField(max_length=20)
    color = models.CharField(max_length=120)
    color_hex = models.CharField(max_length=20)
    image_url = models.URLField(blank=True)
    stock = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__name", "color", "size", "sku"]

    def __str__(self) -> str:
        return f"{self.product.name} - {self.color} / {self.size}"
