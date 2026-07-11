from django.db import models
from django.contrib.auth import get_user_model

from apps.management.models import Branch

User = get_user_model()


class StaffProfile(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
	branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
	can_override_branch = models.BooleanField(default=False)
	preferred_language = models.CharField(max_length=5, default="en")

	def __str__(self):
		return self.user.username
