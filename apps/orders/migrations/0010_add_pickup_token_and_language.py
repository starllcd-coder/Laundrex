from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_customer_whatsapp_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="preferred_language",
            field=models.CharField(default="en", max_length=2),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_token",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True, db_index=True),
        ),
    ]
