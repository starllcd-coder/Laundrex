from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
        ("management", "0005_branch_name_ar"),
    ]

    operations = [
        migrations.CreateModel(
            name="BranchItemServicePrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price", models.DecimalField(decimal_places=3, default=0, max_digits=10)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="prices", to="management.branch")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="branch_prices", to="catalog.item")),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="catalog.service")),
            ],
            options={
                "unique_together": {("branch", "item", "service")},
            },
        ),
    ]
