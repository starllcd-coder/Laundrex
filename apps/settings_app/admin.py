from django.contrib import admin

from .models import WhatsAppSettings, WhatsAppTemplate, WhatsAppMessageLog, SyncSettings, BankTransferSettings


@admin.register(WhatsAppSettings)
class WhatsAppSettingsAdmin(admin.ModelAdmin):
	list_display = ("enabled", "sender_name", "allow_manual_send")


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
	list_display = ("key", "name", "enabled", "template_name_en", "template_name_ar")
	list_filter = ("enabled",)
	search_fields = ("key", "name")


@admin.register(WhatsAppMessageLog)
class WhatsAppMessageLogAdmin(admin.ModelAdmin):
	list_display = ("created_at", "to_number", "template_key", "status", "provider_message_id")
	list_filter = ("status", "template_key")
	search_fields = ("to_number", "provider_message_id")


@admin.register(SyncSettings)
class SyncSettingsAdmin(admin.ModelAdmin):
	list_display = ("enabled", "endpoints_enabled", "cloud_base_url", "interval_seconds", "updated_at")
	search_fields = ("cloud_base_url",)


@admin.register(BankTransferSettings)
class BankTransferSettingsAdmin(admin.ModelAdmin):
	list_display = ("enabled", "bank_name", "account_name", "iban", "updated_at")
	search_fields = ("bank_name", "account_name", "account_number", "iban")
