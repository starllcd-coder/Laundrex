from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0011_delivery_zone_and_eta"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_lat",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_lng",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
