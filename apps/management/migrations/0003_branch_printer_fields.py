from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0002_seed_branches"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="receipt_header",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="branch",
            name="receipt_footer",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="branch",
            name="vat_number",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="branch",
            name="printer_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="branch",
            name="receipt_copies",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="branch",
            name="receipt_template",
            field=models.CharField(default="80mm", max_length=10),
        ),
    ]
