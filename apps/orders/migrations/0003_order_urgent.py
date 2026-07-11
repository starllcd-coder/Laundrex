from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_orderstatuslog"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="urgent",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
