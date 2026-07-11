from django.contrib import admin

from .models import CustomerAccount, SavedAddress, PhoneOTP, DeviceToken, MobileOrderMeta, MobileEvent, MobileNotification


@admin.register(CustomerAccount)
class CustomerAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "customer", "phone", "created_at")
    search_fields = ("user__username", "user__email", "customer__name", "phone")


@admin.register(SavedAddress)
class SavedAddressAdmin(admin.ModelAdmin):
    list_display = ("label", "customer", "city", "area", "is_default")
    list_filter = ("city", "is_default")
    search_fields = ("customer__name", "customer__phone", "label", "area", "address_line_1")


@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ("phone", "purpose", "code", "is_used", "expires_at", "created_at")
    list_filter = ("purpose", "is_used")
    search_fields = ("phone", "code")


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ("customer", "platform", "token", "created_at")
    search_fields = ("customer__phone", "token")


@admin.register(MobileOrderMeta)
class MobileOrderMetaAdmin(admin.ModelAdmin):
    list_display = ("order", "payment_method", "promo_code", "promo_discount", "points_used", "created_at")
    search_fields = ("order__order_no", "promo_code", "transfer_reference")


@admin.register(MobileEvent)
class MobileEventAdmin(admin.ModelAdmin):
    list_display = ("name", "customer", "created_at")
    list_filter = ("name",)
    search_fields = ("name", "customer__name", "customer__phone")


@admin.register(MobileNotification)
class MobileNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "customer", "order", "event_code", "is_read", "created_at")
    list_filter = ("is_read", "event_code")
    search_fields = ("title", "message", "customer__name", "customer__phone", "order__order_no")
