from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("management", "0005_branch_name_ar"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="delivery_slot_templates",
            field=models.TextField(blank=True, default=""),
        ),
    ]
