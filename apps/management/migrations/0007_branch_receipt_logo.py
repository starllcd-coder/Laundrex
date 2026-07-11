from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0006_delivery_slot_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="receipt_logo",
            field=models.FileField(blank=True, null=True, upload_to="branch_receipt_logos/"),
        ),
    ]

