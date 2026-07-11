from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ("order", "method", "amount", "created_by", "created_at")
	list_filter = ("method",)
	search_fields = ("order__order_no", "order__customer__name", "order__customer__phone", "reference")
