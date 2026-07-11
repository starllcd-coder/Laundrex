from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_recalculate_order_balance"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="notes",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="customer",
            name="points",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="customer",
            name="vip_discount_percent",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="order",
            name="loyalty_points_awarded",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="order",
            name="points_awarded",
            field=models.BooleanField(default=False),
        ),
    ]
