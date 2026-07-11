from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_order_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="whatsapp_opt_in",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customer",
            name="whatsapp_number",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="customer",
            name="whatsapp_opt_in_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
