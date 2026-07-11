from django.db import migrations


def recalc_balance(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.all():
        due = order.total - order.paid
        order.balance = due if due > 0 else 0
        order.save(update_fields=["balance"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_order_urgent"),
    ]

    operations = [
        migrations.RunPython(recalc_balance, migrations.RunPython.noop),
    ]
