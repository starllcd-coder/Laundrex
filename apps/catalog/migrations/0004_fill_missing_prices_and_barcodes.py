from decimal import Decimal

from django.db import migrations


CORE_SERVICE_CODES = ("wash", "wash_iron", "iron", "dryclean")


def default_wash_price(item_name: str) -> Decimal:
    name = (item_name or "").lower()
    if any(k in name for k in ["wedding", "gown", "evening"]):
        return Decimal("4.500")
    if any(k in name for k in ["carpet (large)", "comforter", "duvet"]):
        return Decimal("3.800")
    if any(k in name for k in ["carpet", "curtain (heavy)", "blanket (heavy)", "sofa cover"]):
        return Decimal("3.000")
    if any(k in name for k in ["curtain", "blanket", "bedsheet", "mattress", "tablecloth", "car seat"]):
        return Decimal("2.000")
    if any(k in name for k in ["suit", "abaya", "dishdasha", "kandura", "jacket", "coat", "blazer"]):
        return Decimal("1.400")
    if any(k in name for k in ["shoes", "bag", "backpack", "school bag"]):
        return Decimal("1.200")
    if any(k in name for k in ["dress", "jalabiya", "hoodie", "sweater"]):
        return Decimal("1.100")
    if any(k in name for k in ["pillow", "towel", "prayer mat", "stuffed toys"]):
        return Decimal("0.800")
    return Decimal("0.600")


def service_price(base: Decimal, service_code: str) -> Decimal:
    if service_code == "wash":
        return base
    if service_code == "wash_iron":
        return base + Decimal("0.300")
    if service_code == "iron":
        return max(Decimal("0.250"), base * Decimal("0.5"))
    if service_code == "dryclean":
        return base + Decimal("0.900")
    return base


def next_barcode(item_id: int, used: set[str]) -> str:
    base = f"ITM{item_id:04d}"
    if base not in used:
        return base
    i = 1
    while True:
        candidate = f"{base}-{i}"
        if candidate not in used:
            return candidate
        i += 1


def fill_missing_prices_and_barcodes(apps, schema_editor):
    Service = apps.get_model("catalog", "Service")
    Item = apps.get_model("catalog", "Item")
    ItemServicePrice = apps.get_model("catalog", "ItemServicePrice")
    BarcodeMap = apps.get_model("catalog", "BarcodeMap")

    services = {
        s.code: s
        for s in Service.objects.filter(code__in=CORE_SERVICE_CODES)
    }
    for item in Item.objects.all():
        base = default_wash_price(item.name)
        for code in CORE_SERVICE_CODES:
            service = services.get(code)
            if not service:
                continue
            ItemServicePrice.objects.get_or_create(
                item=item,
                service=service,
                defaults={"price": service_price(base, code)},
            )

    used = set(BarcodeMap.objects.values_list("barcode", flat=True))
    mapped_item_ids = set(BarcodeMap.objects.values_list("item_id", flat=True))
    for item in Item.objects.exclude(id__in=mapped_item_ids):
        barcode = next_barcode(item.id, used)
        BarcodeMap.objects.create(
            barcode=barcode,
            item=item,
            is_active=True,
        )
        used.add(barcode)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_bilingual_catalog_and_oman_items"),
    ]

    operations = [
        migrations.RunPython(fill_missing_prices_and_barcodes, migrations.RunPython.noop),
    ]
