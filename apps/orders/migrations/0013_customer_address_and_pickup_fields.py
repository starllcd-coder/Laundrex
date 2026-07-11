from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0012_delivery_lat_lng"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="address",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="customer",
            name="address2",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_slot",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_notes",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
