from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_order_delivery_fields"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="order",
            options={
                "permissions": [
                    ("view_all_branches", "Can view all branches"),
                    ("can_discount", "Can apply discount"),
                    ("can_refund", "Can cancel or refund orders"),
                    ("can_change_status", "Can change order status"),
                    ("can_manage_delivery", "Can manage delivery"),
                    ("can_view_reports", "Can view reports"),
                    ("can_manage_staff", "Can manage staff"),
                    ("can_edit_catalog", "Can edit catalog"),
                ]
            },
        ),
    ]
