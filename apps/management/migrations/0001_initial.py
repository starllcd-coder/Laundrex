from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Branch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("active", models.BooleanField(default=True)),
                ("address", models.CharField(blank=True, default="", max_length=255)),
                ("phone", models.CharField(blank=True, default="", max_length=40)),
                ("tax_rate", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("allow_discounts", models.BooleanField(default=True)),
                ("max_discount_percent", models.DecimalField(decimal_places=2, default=30, max_digits=5)),
            ],
        ),
    ]
