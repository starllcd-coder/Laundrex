from django.contrib import admin
from .models import Service, Item, ItemServicePrice, BranchItemServicePrice, BarcodeMap


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "name_ar", "is_active", "sort_order")
    list_editable = ("name", "name_ar", "is_active", "sort_order")
    search_fields = ("code", "name", "name_ar")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "name_ar", "is_active", "sort_order")
    list_editable = ("name_ar", "is_active", "sort_order")
    search_fields = ("name", "name_ar")


@admin.register(ItemServicePrice)
class ItemServicePriceAdmin(admin.ModelAdmin):
    list_display = ("item", "service", "price")
    list_editable = ("price",)
    list_filter = ("service",)
    search_fields = ("item__name", "item__name_ar", "service__name", "service__name_ar")


@admin.register(BranchItemServicePrice)
class BranchItemServicePriceAdmin(admin.ModelAdmin):
    list_display = ("branch", "item", "service", "price")
    list_editable = ("price",)
    list_filter = ("branch", "service")
    search_fields = ("branch__code", "branch__name", "item__name", "item__name_ar", "service__name", "service__name_ar")


@admin.register(BarcodeMap)
class BarcodeMapAdmin(admin.ModelAdmin):
    list_display = ("barcode", "item", "is_active")
    list_editable = ("is_active",)
    search_fields = ("barcode", "item__name")
