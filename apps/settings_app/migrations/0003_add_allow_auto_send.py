from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0002_seed_whatsapp_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="whatsappsettings",
            name="allow_auto_send",
            field=models.BooleanField(default=False),
        ),
    ]
