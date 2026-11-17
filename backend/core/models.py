from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from core.base import UUIDModel


class Tenant(UUIDModel):
    class Types(models.TextChoices):
        COOPERATIVE = "cooperative", "Cooperative"
        SACCO = "sacco", "SACCO"
        BUYER = "buyer", "Buyer"

    name = models.CharField(max_length=200, unique=True)
    type = models.CharField(max_length=20, choices=Types.choices, default=Types.COOPERATIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("A phone number is required.")
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Roles.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(phone, password, **extra_fields)


class User(UUIDModel, AbstractBaseUser, PermissionsMixin):
    class Roles(models.TextChoices):
        FARMER = "farmer", "Farmer"
        AGENT = "agent", "Storage agent"
        COOP_ADMIN = "coop_admin", "Cooperative admin"
        ADMIN = "admin", "Admin"

    phone = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.FARMER)
    tenant = models.ForeignKey(
        Tenant, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["name"]
    objects = UserManager()

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Ward(UUIDModel):
    class Regions(models.TextChoices):
        SOUTH_EASTERN = "south_eastern", "South Eastern"
        METROPOLITAN = "metropolitan", "Metropolitan"
        OTHER = "other", "Other"

    name = models.CharField(max_length=150)
    county = models.CharField(max_length=100)
    region = models.CharField(
        max_length=20, choices=Regions.choices, default=Regions.OTHER, blank=True
    )
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        unique_together = ("name", "county")
        ordering = ("county", "name")

    def __str__(self):
        return f"{self.name}, {self.county}"


class Crop(UUIDModel):
    code = models.CharField(max_length=30, unique=True)
    name_en = models.CharField(max_length=100)
    name_sw = models.CharField(max_length=100)
    storable = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def __str__(self):
        return self.name_en


class Farmer(UUIDModel):
    user = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="farmer_profile"
    )
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, unique=True)
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="farmers")
    tenant = models.ForeignKey(
        Tenant, null=True, blank=True, on_delete=models.SET_NULL, related_name="farmers"
    )
    consent_given = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Plot(UUIDModel):
    farmer = models.ForeignKey(Farmer, on_delete=models.CASCADE, related_name="plots")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="plots")
    acres = models.DecimalField(max_digits=10, decimal_places=2)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.acres} acres - {self.farmer.name}"
