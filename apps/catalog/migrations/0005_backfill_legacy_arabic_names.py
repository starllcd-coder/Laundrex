from django.db import migrations


LEGACY_ITEM_AR = {
    "Shirt": "قميص",
    "Pant": "بنطال",
    "Kandura": "كندورة",
    "Abaya": "عباية",
    "Bedsheet": "شرشف",
    "Tshirt": "تي شيرت",
    "Jacket": "جاكيت",
    "Suit": "بدلة",
    "Blouse": "بلوزة",
    "Dress": "فستان",
    "Socks": "جوارب",
    "Towel": "منشفة",
    "Pillowcase": "غطاء وسادة",
    "Curtain": "ستارة",
    "Carpet": "سجادة",
    "Comforter": "لحاف",
    "Blanket": "بطانية",
}

LEGACY_SERVICE_AR = {
    "wash": "غسيل",
    "wash_iron": "غسيل + كي",
    "iron": "كي فقط",
    "dryclean": "تنظيف جاف",
}


def backfill_legacy_arabic_names(apps, schema_editor):
    Item = apps.get_model("catalog", "Item")
    Service = apps.get_model("catalog", "Service")

    for name, ar in LEGACY_ITEM_AR.items():
        Item.objects.filter(name=name, name_ar="").update(name_ar=ar)

    for code, ar in LEGACY_SERVICE_AR.items():
        Service.objects.filter(code=code, name_ar="").update(name_ar=ar)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_fill_missing_prices_and_barcodes"),
    ]

    operations = [
        migrations.RunPython(backfill_legacy_arabic_names, migrations.RunPython.noop),
    ]
