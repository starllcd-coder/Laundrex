from django.db import migrations


def seed_default_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    order_ct = ContentType.objects.filter(app_label="orders", model="order").first()
    if not order_ct:
        return

    all_codes = [
        "view_all_branches",
        "can_discount",
        "can_refund",
        "can_change_status",
        "can_manage_delivery",
        "can_view_reports",
        "can_manage_staff",
        "can_edit_catalog",
    ]

    perms = Permission.objects.filter(content_type=order_ct, codename__in=all_codes)
    perms_map = {p.codename: p for p in perms}

    role_defs = {
        "Admin": all_codes,
        "Manager": [
            "view_all_branches",
            "can_discount",
            "can_refund",
            "can_change_status",
            "can_manage_delivery",
            "can_view_reports",
            "can_manage_staff",
            "can_edit_catalog",
        ],
        "Cashier": ["can_discount", "can_change_status"],
        "Worker": ["can_change_status"],
    }

    for name, codes in role_defs.items():
        group, _ = Group.objects.get_or_create(name=name)
        group.permissions.set([perms_map[c] for c in codes if c in perms_map])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0011_populate_pickup_token"),
    ]

    operations = [
        migrations.RunPython(seed_default_roles, migrations.RunPython.noop),
    ]
