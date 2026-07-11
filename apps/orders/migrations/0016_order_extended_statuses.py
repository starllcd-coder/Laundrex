from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0015_add_sync_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("RECEIVED", "Received"),
                    ("ACCEPTED", "Accepted"),
                    ("PICKUP_ASSIGNED", "Pickup assigned"),
                    ("WASHING", "Washing"),
                    ("IRONING", "Ironing"),
                    ("READY", "Ready"),
                    ("OUT_FOR_DELIVERY", "Out for delivery"),
                    ("DELIVERED", "Delivered"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="RECEIVED",
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="orderstatuslog",
            name="from_status",
            field=models.CharField(blank=True, default="", max_length=24),
        ),
        migrations.AlterField(
            model_name="orderstatuslog",
            name="to_status",
            field=models.CharField(blank=True, default="", max_length=24),
        ),
    ]
