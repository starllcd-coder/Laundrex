from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_customer_loyalty_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="points_redeemed",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="order",
            name="points_redeemed_value",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=10),
        ),
    ]
