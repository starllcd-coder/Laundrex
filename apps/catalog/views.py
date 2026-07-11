from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
import re

from .models import Service, Item, ItemServicePrice, BranchItemServicePrice, BarcodeMap
from apps.accounts.utils import get_effective_branch
from apps.management.models import Branch

CORE_SERVICE_CODES = ("wash", "wash_iron", "iron", "dryclean")
MOBILE_EXTRA_SERVICE_CODES = (
    "express",
    "stain_removal",
    "perfumed_wash",
    "hypoallergenic_wash",
    "separate_wash",
)


def _fallback_service_name_ar(service) -> str:
    by_code = {
        "wash": "غسيل",
        "wash_iron": "غسيل + كي",
        "iron": "كي فقط",
        "dryclean": "تنظيف جاف",
        "express": "خدمة سريعة (نفس اليوم)",
        "stain_removal": "إزالة البقع",
        "perfumed_wash": "غسيل معطر",
        "hypoallergenic_wash": "غسيل مضاد للحساسية (آمن للأطفال)",
        "separate_wash": "غسيل منفصل (بدون خلط)",
    }
    code = (getattr(service, "code", "") or "").strip().lower()
    if code in by_code:
        return by_code[code]
    name = (getattr(service, "name", "") or "").strip().lower()
    if "wash" in name and "iron" in name:
        return "غسيل + كي"
    if "dry" in name:
        return "تنظيف جاف"
    if name == "wash":
        return "غسيل"
    if name == "iron":
        return "كي فقط"
    return getattr(service, "name_ar", "") or ""


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


def _ensure_core_prices_for_all_items():
    service_codes = CORE_SERVICE_CODES + MOBILE_EXTRA_SERVICE_CODES
    services = {x.code: x for x in Service.objects.filter(code__in=service_codes)}
    if not services:
        return
    for item in Item.objects.all():
        wash = _default_wash_price_for_item(item.name)
        for code in service_codes:
            service = services.get(code)
            if not service:
                continue
            ItemServicePrice.objects.get_or_create(
                item=item,
                service=service,
                defaults={"price": _service_price_from_wash(wash, code)},
            )


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


def _normalize_legacy_itm_barcodes():
    used = set(BarcodeMap.objects.values_list("barcode", flat=True))
    legacy_rows = BarcodeMap.objects.select_related("item").filter(barcode__startswith="ITM").order_by("item__sort_order", "item__name", "id")
    for row in legacy_rows:
        # If item already has a readable barcode, remove/deactivate legacy one.
        alt = BarcodeMap.objects.filter(item=row.item, is_active=True).exclude(pk=row.pk).exclude(barcode__startswith="ITM").first()
        if alt:
            row.is_active = False
            row.save(update_fields=["is_active"])
            continue
        old = row.barcode
        used.discard(old)
        new_code = _next_barcode_for_item(row.item.name, used)
        row.barcode = new_code
        row.is_active = True
        row.save(update_fields=["barcode", "is_active"])
        used.add(new_code)


def _ensure_barcodes_for_all_items():
    _normalize_legacy_itm_barcodes()
    used = set(BarcodeMap.objects.values_list("barcode", flat=True))
    mapped_item_ids = set(BarcodeMap.objects.values_list("item_id", flat=True))
    for item in Item.objects.exclude(id__in=mapped_item_ids):
        code = _next_barcode_for_item(item.name, used)
        BarcodeMap.objects.create(barcode=code, item=item, is_active=True)
        used.add(code)


@login_required
def catalog_home(request):
    _normalize_legacy_itm_barcodes()
    services = Service.objects.order_by("sort_order", "name")
    items = Item.objects.order_by("sort_order", "name")
    prices = ItemServicePrice.objects.select_related("item", "service").order_by("item__name", "service__name")
    barcodes = BarcodeMap.objects.select_related("item").order_by("barcode")

    if str(getattr(request, "LANGUAGE_CODE", "")).lower().startswith("ar"):
        for s in services:
            if not s.name_ar:
                s.name_ar = _fallback_service_name_ar(s)
        for p in prices:
            if not p.service.name_ar:
                p.service.name_ar = _fallback_service_name_ar(p.service)

    return render(request, "catalog/home.html", {
        "services": services,
        "items": items,
        "prices": prices,
        "barcodes": barcodes,
    })


@login_required
@permission_required("orders.can_edit_catalog", raise_exception=True)
@require_POST
def seed_defaults(request):
    # Services
    defaults = [
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
    for code, name, name_ar, s in defaults:
        service, created = Service.objects.get_or_create(
            code=code,
            defaults={"name": name, "name_ar": name_ar, "sort_order": s},
        )
        if not created:
            changed = False
            if not service.name:
                service.name = name
                changed = True
            if not service.name_ar:
                service.name_ar = name_ar
                changed = True
            if service.sort_order != s:
                service.sort_order = s
                changed = True
            if changed:
                service.save(update_fields=["name", "name_ar", "sort_order"])

    # Items
    catalog_items = [
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
    for name, name_ar, s in catalog_items:
        item, created = Item.objects.get_or_create(
            name=name,
            defaults={"name_ar": name_ar, "sort_order": s},
        )
        if not created:
            changed = False
            if not item.name_ar:
                item.name_ar = name_ar
                changed = True
            if item.sort_order != s:
                item.sort_order = s
                changed = True
            if changed:
                item.save(update_fields=["name_ar", "sort_order"])

    # Basic prices (edit later in Admin)
    services = {x.code: x for x in Service.objects.all()}
    items = {x.name: x for x in Item.objects.all()}

    base = {
        "Shirt (Casual)": {"wash": "0.500", "wash_iron": "0.800", "iron": "0.300", "dryclean": "1.200"},
        "Trousers / Pants": {"wash": "0.600", "wash_iron": "0.900", "iron": "0.350", "dryclean": "1.300"},
        "Kandura / Dishdasha (Premium)": {"wash": "1.000", "wash_iron": "1.300", "iron": "0.600", "dryclean": "1.800"},
        "Abaya (Regular)": {"wash": "1.200", "wash_iron": "1.500", "iron": "0.700", "dryclean": "2.000"},
        "Bedsheet (Single)": {"wash": "0.800", "wash_iron": "1.100", "iron": "0.500", "dryclean": "1.600"},
        "T-Shirt": {"wash": "0.450", "wash_iron": "0.700", "iron": "0.250", "dryclean": "1.100"},
        "Jeans": {"wash": "0.700", "wash_iron": "1.000", "iron": "0.400", "dryclean": "1.500"},
        "Jacket (Light)": {"wash": "1.200", "wash_iron": "1.600", "iron": "0.900", "dryclean": "2.500"},
        "Suit (2-piece)": {"wash": "1.800", "wash_iron": "2.200", "iron": "1.200", "dryclean": "3.200"},
        "Skirt": {"wash": "0.700", "wash_iron": "1.000", "iron": "0.400", "dryclean": "1.500"},
        "Dress (Simple)": {"wash": "1.200", "wash_iron": "1.600", "iron": "0.800", "dryclean": "2.400"},
        "Shorts": {"wash": "0.500", "wash_iron": "0.800", "iron": "0.300", "dryclean": "1.200"},
        "Towel (Small)": {"wash": "0.500", "wash_iron": "0.700", "iron": "0.250", "dryclean": "1.000"},
        "Pillow Cover": {"wash": "0.350", "wash_iron": "0.500", "iron": "0.200", "dryclean": "0.800"},
        "Curtain (Light)": {"wash": "2.000", "wash_iron": "2.500", "iron": "1.200", "dryclean": "3.500"},
        "Carpet (Small)": {"wash": "3.500", "wash_iron": "4.200", "iron": "0.000", "dryclean": "5.000"},
        "Comforter / Duvet": {"wash": "2.500", "wash_iron": "3.000", "iron": "1.500", "dryclean": "4.000"},
        "Blanket (Light)": {"wash": "1.800", "wash_iron": "2.200", "iron": "1.000", "dryclean": "3.200"},
    }

    for item_name, per in base.items():
        for svc_code, price in per.items():
            ItemServicePrice.objects.get_or_create(
                item=items[item_name],
                service=services[svc_code],
                defaults={"price": price},
            )

    # Ensure full catalog is usable even when new items are added later.
    _ensure_core_prices_for_all_items()
    _ensure_barcodes_for_all_items()

    return redirect("catalog:home")


@login_required
def pos_data_api(request):
    """
    POS needs:
      - services list
      - items list
      - barcode -> item_id map
      - (item_id, service_code) -> price map
    """
    services = list(
        Service.objects.filter(is_active=True).exclude(code="")
        .order_by("sort_order", "name")
        .values("id", "code", "name", "name_ar")
    )

    items = list(
        Item.objects.filter(is_active=True)
        .order_by("sort_order", "name")
        .values("id", "name", "name_ar")
    )

    barcode_map = {}
    for b in BarcodeMap.objects.select_related("item").filter(is_active=True):
        barcode_map[b.barcode.upper()] = b.item_id

    price_map = {}
    for p in ItemServicePrice.objects.select_related("item", "service"):
        price_map[f"{p.item_id}:{p.service.code}"] = str(p.price)

    branch_code = (get_effective_branch(request) or request.session.get("active_branch") or "").strip()
    branch = Branch.objects.filter(code=branch_code).first() if branch_code else None
    if branch:
        for p in BranchItemServicePrice.objects.select_related("item", "service").filter(branch=branch):
            price_map[f"{p.item_id}:{p.service.code}"] = str(p.price)

    return JsonResponse({
        "services": services,
        "items": items,
        "barcode_map": barcode_map,
        "price_map": price_map,
    })
