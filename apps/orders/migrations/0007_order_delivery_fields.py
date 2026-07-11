from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_order_points_redeemed"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_required",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_status",
            field=models.CharField(choices=[("PENDING", "Pending"), ("ASSIGNED", "Assigned"), ("OUT", "Out for delivery"), ("DELIVERED", "Delivered"), ("FAILED", "Failed"), ("CANCELLED", "Cancelled")], default="PENDING", max_length=12),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_address",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_phone",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_slot",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_fee",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_driver_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_driver_phone",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_notes",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="order",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
