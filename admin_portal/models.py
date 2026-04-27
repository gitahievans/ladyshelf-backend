from django.db import models


class AdminStaffAccess(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ATTENDANT = "attendant", "Attendant"

    customer = models.OneToOneField(
        "customers.CustomerProfile",
        on_delete=models.CASCADE,
        related_name="admin_staff_access",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["customer__email"]
        verbose_name = "admin staff access"
        verbose_name_plural = "admin staff access"

    def __str__(self) -> str:
        return f"{self.customer.email} ({self.role})"

