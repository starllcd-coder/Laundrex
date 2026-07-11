from django.db import models

from apps.management.models import Branch

class Service(models.Model):
    code = models.CharField(max_length=40, unique=True)   # wash, wash_iron, iron, dryclean
    name = models.CharField(max_length=80)               # Wash, Wash + Iron...
    name_ar = models.CharField(max_length=80, blank=True, default="")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=10)

    def __str__(self):
        return self.name


class Item(models.Model):
    name = models.CharField(max_length=120, unique=True)
    name_ar = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=10)

    def __str__(self):
        return self.name


class ItemServicePrice(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="prices")
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    class Meta:
        unique_together = ("item", "service")

    def __str__(self):
        return f"{self.item} - {self.service} = {self.price}"


class BranchItemServicePrice(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="prices")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="branch_prices")
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=3, default=0)

    class Meta:
        unique_together = ("branch", "item", "service")

    def __str__(self):
        return f"{self.branch.code} {self.item} - {self.service} = {self.price}"


class BarcodeMap(models.Model):
    barcode = models.CharField(max_length=80, unique=True, db_index=True)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.barcode} → {self.item}"
