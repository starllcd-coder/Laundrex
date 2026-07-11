from django.db import migrations, models


def seed_branch_name_ar(apps, schema_editor):
    Branch = apps.get_model("management", "Branch")
    fallback = {
        "muscat": "مسقط",
        "salalah": "صلالة",
        "seeb": "السيب",
    }

    for branch in Branch.objects.all():
        if branch.name_ar:
            continue
        by_name = fallback.get((branch.name or "").strip().lower())
        by_code = fallback.get((branch.code or "").strip().lower())
        branch.name_ar = by_name or by_code or ""
        branch.save(update_fields=["name_ar"])


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0004_auditlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="name_ar",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.RunPython(seed_branch_name_ar, migrations.RunPython.noop),
    ]
