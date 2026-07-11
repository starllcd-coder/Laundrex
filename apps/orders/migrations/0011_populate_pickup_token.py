import secrets
from django.db import migrations, models


def populate_tokens(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    qs = Order.objects.filter(pickup_token__isnull=True)
    for order in qs.iterator():
        token = secrets.token_urlsafe(18)
        while Order.objects.filter(pickup_token=token).exists():
            token = secrets.token_urlsafe(18)
        order.pickup_token = token
        order.save(update_fields=["pickup_token"])


def remove_tokens(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.update(pickup_token=None)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0010_add_pickup_token_and_language"),
    ]

    operations = [
        migrations.RunPython(populate_tokens, remove_tokens),
        migrations.AlterField(
            model_name="order",
            name="pickup_token",
            field=models.CharField(blank=True, max_length=64, null=False, unique=True, db_index=True),
        ),
    ]
