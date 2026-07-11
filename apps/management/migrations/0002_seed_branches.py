from django.db import migrations


def seed_branches(apps, schema_editor):
    Branch = apps.get_model("management", "Branch")
    if Branch.objects.exists():
        return

    defaults = [
        ("muscat", "Muscat"),
        ("seeb", "Seeb"),
        ("salalah", "Salalah"),
    ]

    for code, name in defaults:
        Branch.objects.create(code=code, name=name, active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_branches, migrations.RunPython.noop),
    ]
