from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0010_add_pickup_token_and_language"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_zone",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="order",
            name="estimated_ready_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
