from django.db import migrations


CORE_SERVICE_CODES = ("wash", "wash_iron", "iron", "dryclean")
MOBILE_EXTRA_SERVICE_CODES = (
    "express",
    "stain_removal",
    "perfumed_wash",
    "hypoallergenic_wash",
    "separate_wash",
)


def _default_wash_price_for_item(item_name: str) -> str:
    name = (item_name or "").lower()
    if any(k in name for k in ["wedding", "gown", "evening"]):
        return "4.500"
    if any(k in name for k in ["carpet (large)", "comforter", "duvet"]):
        return "3.800"
    if any(k in name for k in ["carpet", "curtain (heavy)", "blanket (heavy)", "sofa cover"]):
        return "3.000"
    if any(k in name for k in ["curtain", "blanket", "bedsheet", "mattress", "tablecloth", "car seat"]):
        return "2.000"
    if any(k in name for k in ["suit", "abaya", "dishdasha", "kandura", "jacket", "coat", "blazer"]):
        return "1.400"
    if any(k in name for k in ["shoes", "bag", "backpack", "school bag"]):
        return "1.200"
    if any(k in name for k in ["dress", "jalabiya", "hoodie", "sweater"]):
        return "1.100"
    if any(k in name for k in ["pillow", "towel", "prayer mat", "stuffed toys"]):
        return "0.800"
    return "0.600"


def _service_price_from_wash(base_wash: str, service_code: str) -> str:
    base = float(base_wash)
    if service_code == "wash":
        return f"{base:.3f}"
    if service_code == "wash_iron":
        return f"{(base + 0.300):.3f}"
    if service_code == "iron":
        return f"{max(0.250, base * 0.5):.3f}"
    if service_code == "dryclean":
        return f"{(base + 0.900):.3f}"
    if service_code == "express":
        return f"{(base + 0.600):.3f}"
    if service_code == "stain_removal":
        return f"{(base + 0.400):.3f}"
    if service_code == "perfumed_wash":
        return f"{(base + 0.200):.3f}"
    if service_code == "hypoallergenic_wash":
        return f"{(base + 0.250):.3f}"
    if service_code == "separate_wash":
        return f"{(base + 0.500):.3f}"
    return f"{base:.3f}"


def fill_missing_mobile_service_prices(apps, schema_editor):
    Service = apps.get_model("catalog", "Service")
    Item = apps.get_model("catalog", "Item")
    ItemServicePrice = apps.get_model("catalog", "ItemServicePrice")

    service_codes = CORE_SERVICE_CODES + MOBILE_EXTRA_SERVICE_CODES
    services = {x.code: x for x in Service.objects.filter(code__in=service_codes)}
    if not services:
        return

    for item in Item.objects.all():
        wash = _default_wash_price_for_item(getattr(item, "name", ""))
        for code in service_codes:
            service = services.get(code)
            if not service:
                continue
            ItemServicePrice.objects.get_or_create(
                item=item,
                service=service,
                defaults={"price": _service_price_from_wash(wash, code)},
            )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_normalize_legacy_itm_barcodes"),
    ]

    operations = [
        migrations.RunPython(fill_missing_mobile_service_prices, migrations.RunPython.noop),
    ]

