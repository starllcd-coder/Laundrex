from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ErrorLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("level", models.CharField(default="ERROR", max_length=20)),
                ("message", models.CharField(blank=True, default="", max_length=255)),
                ("path", models.CharField(blank=True, default="", max_length=255)),
                ("method", models.CharField(blank=True, default="", max_length=10)),
                ("branch_code", models.CharField(blank=True, default="", max_length=80)),
                ("traceback", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
