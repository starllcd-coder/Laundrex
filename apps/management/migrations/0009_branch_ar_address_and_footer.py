from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0008_branch_cr_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="address_ar",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="branch",
            name="receipt_footer_ar",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]

