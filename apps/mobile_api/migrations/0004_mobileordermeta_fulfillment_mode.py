from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mobile_api", "0003_alter_phoneotp_purpose_mobileevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="mobileordermeta",
            name="fulfillment_mode",
            field=models.CharField(blank=True, default="DELIVERY", max_length=20),
        ),
    ]
