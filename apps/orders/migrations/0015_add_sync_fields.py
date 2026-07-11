from django.db import migrations, models
import uuid


def populate_sync_uids(apps, schema_editor):
    Customer = apps.get_model("orders", "Customer")
    for customer in Customer.objects.all().iterator():
        customer.sync_uid = str(uuid.uuid4())
        customer.save(update_fields=["sync_uid"])


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0014_merge_orders_branches"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="sync_uid",
            field=models.CharField(default=uuid.uuid4, max_length=36),
        ),
        migrations.AddField(
            model_name="customer",
            name="cloud_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="order",
            name="cloud_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(populate_sync_uids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customer",
            name="sync_uid",
            field=models.CharField(default=uuid.uuid4, max_length=36, unique=True),
        ),
    ]
