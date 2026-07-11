from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from apps.orders.models import Order


ROLE_PERMISSIONS = {
    "Admin": [
        "view_all_branches",
        "can_discount",
        "can_refund",
        "can_change_status",
        "can_manage_delivery",
        "can_view_reports",
        "can_manage_staff",
        "can_edit_catalog",
    ],
    "Manager": [
        "view_all_branches",
        "can_discount",
        "can_refund",
        "can_change_status",
        "can_manage_delivery",
        "can_view_reports",
    ],
    "Cashier": [
        "can_discount",
        "can_change_status",
        "can_manage_delivery",
    ],
    "Worker": [
        "can_change_status",
    ],
}


def create_roles(sender, **kwargs):
    content_type = ContentType.objects.get_for_model(Order)
    for role, perms in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role)
        for codename in perms:
            perm = Permission.objects.filter(content_type=content_type, codename=codename).first()
            if perm:
                group.permissions.add(perm)
