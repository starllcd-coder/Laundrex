from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ErrorLog(models.Model):
    level = models.CharField(max_length=20, default="ERROR")
    message = models.CharField(max_length=255, blank=True, default="")
    path = models.CharField(max_length=255, blank=True, default="")
    method = models.CharField(max_length=10, blank=True, default="")
    branch_code = models.CharField(max_length=80, blank=True, default="")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    traceback = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.level} {self.path}"


class SyncState(models.Model):
    key = models.CharField(max_length=64, unique=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key


class ResetAuditLog(models.Model):
    SCOPE_CHOICES = (
        ("all", "All branches"),
        ("branch", "Single branch"),
    )

    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="all")
    branch_code = models.CharField(max_length=40, blank=True, default="")
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    confirmation_text = models.CharField(max_length=120, blank=True, default="")
    deleted_counts = models.JSONField(default=dict, blank=True)
    message = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.scope == "branch" and self.branch_code:
            return f"Reset {self.branch_code} by {self.triggered_by or '-'}"
        return f"Reset ALL by {self.triggered_by or '-'}"
