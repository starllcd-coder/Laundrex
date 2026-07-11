from django.db import migrations, models


SERVICES = [
    ("wash", "Wash", "غسيل", 10),
    ("wash_iron", "Wash + Iron", "غسيل + كي", 20),
    ("iron", "Iron", "كي فقط", 30),
    ("dryclean", "Dry Clean", "تنظيف جاف", 40),
    ("express", "Express Service (Same Day)", "خدمة سريعة (نفس اليوم)", 50),
    ("stain_removal", "Stain Removal", "إزالة البقع", 60),
    ("perfumed_wash", "Perfumed Wash", "غسيل معطر", 70),
    ("hypoallergenic_wash", "Hypoallergenic Wash (Baby-safe)", "غسيل مضاد للحساسية (آمن للأطفال)", 80),
    ("separate_wash", "Separate Wash (No Mix)", "غسيل منفصل (بدون خلط)", 90),
]

ITEMS = [
    ("T-Shirt", "تي شيرت", 10),
    ("Shirt (Casual)", "قميص (كاجوال)", 20),
    ("Shirt (Formal)", "قميص (رسمي)", 30),
    ("Polo Shirt", "قميص بولو", 40),
    ("Jeans", "جينز", 50),
    ("Trousers / Pants", "بنطال", 60),
    ("Shorts", "شورت", 70),
    ("Skirt", "تنورة", 80),
    ("Dress (Simple)", "فستان (عادي)", 90),
    ("Abaya (Regular)", "عباية (عادية)", 100),
    ("Dishdasha", "دشداشة", 110),
    ("Jacket (Light)", "جاكيت (خفيف)", 120),
    ("Jacket (Heavy / Winter)", "جاكيت (ثقيل / شتوي)", 130),
    ("Coat", "معطف", 140),
    ("Sweater", "كنزة", 150),
    ("Hoodie", "هودي", 160),
    ("Suit (2-piece)", "بدلة (قطعتان)", 170),
    ("Suit (3-piece)", "بدلة (ثلاث قطع)", 180),
    ("Blazer", "بليزر", 190),
    ("Abaya (Fancy / Embroidered)", "عباية (فاخرة / مطرزة)", 200),
    ("Jalabiya", "جلابية", 210),
    ("Kandura / Dishdasha (Premium)", "كندورة / دشداشة (فاخر)", 220),
    ("Scarf / Sheila / Hijab", "وشاح / شيلة / حجاب", 230),
    ("Wedding Dress", "فستان زفاف", 240),
    ("Evening Gown", "فستان سهرة", 250),
    ("Bedsheet (Single)", "شرشف (مفرد)", 260),
    ("Bedsheet (Double / King)", "شرشف (مزدوج / كينغ)", 270),
    ("Pillow Cover", "غطاء وسادة", 280),
    ("Pillow", "وسادة", 290),
    ("Blanket (Light)", "بطانية (خفيفة)", 300),
    ("Blanket (Heavy)", "بطانية (ثقيلة)", 310),
    ("Comforter / Duvet", "لحاف / دوفية", 320),
    ("Mattress Cover", "غطاء مرتبة", 330),
    ("Towel (Small)", "منشفة (صغيرة)", 340),
    ("Towel (Large / Bath)", "منشفة (كبيرة / حمام)", 350),
    ("Curtain (Light)", "ستارة (خفيفة)", 360),
    ("Curtain (Heavy)", "ستارة (ثقيلة)", 370),
    ("Sofa Cover", "غطاء أريكة", 380),
    ("Cushion Cover", "غطاء وسادة ديكور", 390),
    ("Tablecloth", "مفرش طاولة", 400),
    ("Shoes (Sports)", "أحذية رياضية", 410),
    ("Shoes (Leather - cleaning only)", "أحذية جلد (تنظيف فقط)", 420),
    ("Slippers", "شبشب", 430),
    ("Bag / Backpack", "حقيبة / حقيبة ظهر", 440),
    ("School Bag", "حقيبة مدرسية", 450),
    ("Cap / Hat", "قبعة", 460),
    ("Carpet (Small)", "سجادة (صغيرة)", 470),
    ("Carpet (Large)", "سجادة (كبيرة)", 480),
    ("Prayer Mat (Sajjadah)", "سجادة صلاة", 490),
    ("Stuffed Toys", "ألعاب محشوة", 500),
    ("Car Seat Cover", "غطاء مقعد السيارة", 510),
]


def seed_bilingual_catalog(apps, schema_editor):
    Service = apps.get_model("catalog", "Service")
    Item = apps.get_model("catalog", "Item")

    for code, name, name_ar, sort_order in SERVICES:
        service, created = Service.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "name_ar": name_ar,
                "sort_order": sort_order,
            },
        )
        if not created:
            changed = False
            if not service.name:
                service.name = name
                changed = True
            if not service.name_ar:
                service.name_ar = name_ar
                changed = True
            if service.sort_order != sort_order:
                service.sort_order = sort_order
                changed = True
            if changed:
                service.save(update_fields=["name", "name_ar", "sort_order"])

    for name, name_ar, sort_order in ITEMS:
        item, created = Item.objects.get_or_create(
            name=name,
            defaults={
                "name_ar": name_ar,
                "sort_order": sort_order,
            },
        )
        if not created:
            changed = False
            if not item.name_ar:
                item.name_ar = name_ar
                changed = True
            if item.sort_order != sort_order:
                item.sort_order = sort_order
                changed = True
            if changed:
                item.save(update_fields=["name_ar", "sort_order"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_branch_item_service_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="name_ar",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="item",
            name="name_ar",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.RunPython(seed_bilingual_catalog, migrations.RunPython.noop),
    ]
