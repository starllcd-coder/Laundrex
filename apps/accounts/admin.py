from django.contrib import admin

from .models import StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "branch", "can_override_branch")
	list_filter = ("branch", "can_override_branch")
	search_fields = ("user__username",)
