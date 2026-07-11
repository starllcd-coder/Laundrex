from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0007_branch_receipt_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="cr_number",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]

