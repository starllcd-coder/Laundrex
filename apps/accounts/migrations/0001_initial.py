from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("management", "0002_seed_branches"),
    ]

    operations = [
        migrations.CreateModel(
            name="StaffProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("can_override_branch", models.BooleanField(default=False)),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="management.branch")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="staff_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
