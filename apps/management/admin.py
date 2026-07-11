from django.contrib import admin

from .models import Branch, AuditLog


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
	list_display = ("code", "name", "name_ar", "active", "tax_rate", "allow_discounts", "max_discount_percent", "cr_number", "receipt_template", "receipt_copies", "has_receipt_logo")
	list_filter = ("active",)
	search_fields = ("code", "name", "name_ar")

	@admin.display(boolean=True, description="Logo")
	def has_receipt_logo(self, obj):
		return bool(obj.receipt_logo)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
	list_display = ("created_at", "action", "entity_type", "entity_id", "branch", "user")
	list_filter = ("action", "entity_type", "branch")
	search_fields = ("entity_id", "message", "user__username")
