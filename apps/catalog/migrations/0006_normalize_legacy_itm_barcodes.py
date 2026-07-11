from django.db import migrations
import re


def _barcode_prefix_for_item_name(name: str) -> str:
    text = (name or "").strip().upper()
    if not text:
        return "I"
    for ch in text:
        if "A" <= ch <= "Z":
            return ch
    return "I"


def _next_barcode_for_item(item_name: str, used_codes: set[str]) -> str:
    prefix = _barcode_prefix_for_item_name(item_name)
    next_num = 1
    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{3}})$")
    for code in used_codes:
        m = pattern.match((code or "").upper())
        if not m:
            continue
        try:
            next_num = max(next_num, int(m.group(1)) + 1)
        except Exception:
            continue
    while True:
        candidate = f"{prefix}{next_num:03d}"
        if candidate not in used_codes:
            return candidate
        next_num += 1


def normalize_legacy_itm_barcodes(apps, schema_editor):
    BarcodeMap = apps.get_model("catalog", "BarcodeMap")

    used = set(BarcodeMap.objects.values_list("barcode", flat=True))
    legacy_rows = (
        BarcodeMap.objects.select_related("item")
        .filter(barcode__startswith="ITM")
        .order_by("item__sort_order", "item__name", "id")
    )

    for row in legacy_rows:
        alt = (
            BarcodeMap.objects.filter(item=row.item, is_active=True)
            .exclude(pk=row.pk)
            .exclude(barcode__startswith="ITM")
            .first()
        )
        if alt:
            row.is_active = False
            row.save(update_fields=["is_active"])
            continue

        old = row.barcode
        used.discard(old)
        new_code = _next_barcode_for_item(getattr(row.item, "name", ""), used)
        row.barcode = new_code
        row.is_active = True
        row.save(update_fields=["barcode", "is_active"])
        used.add(new_code)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_backfill_legacy_arabic_names"),
    ]

    operations = [
        migrations.RunPython(normalize_legacy_itm_barcodes, migrations.RunPython.noop),
    ]
