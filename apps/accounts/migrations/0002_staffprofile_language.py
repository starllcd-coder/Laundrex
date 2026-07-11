from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffprofile",
            name="preferred_language",
            field=models.CharField(default="en", max_length=5),
        ),
    ]
