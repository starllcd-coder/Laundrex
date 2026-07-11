from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0012_seed_default_roles"),
        ("orders", "0013_customer_address_and_pickup_fields"),
    ]

    operations = []
