import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "laundrex.settings")

try:
    import django
    django.setup()
except Exception as exc:
    print("Failed to set up Django:", exc)
    sys.exit(1)

from django.test import Client
from django.test.utils import override_settings
from apps.management.models import Branch

branch = Branch.objects.filter(active=True).first()
print("Active branch:", branch.code if branch else None)

if not branch:
    print("No active branch found. Create one before testing.")
    sys.exit(1)

with override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"]):
    client = Client()
    username = os.getenv("LAUNDREX_SMOKE_USER", "").strip()
    password = os.getenv("LAUNDREX_SMOKE_PASS", "")
    if not username or not password:
        print("Missing credentials. Set LAUNDREX_SMOKE_USER and LAUNDREX_SMOKE_PASS.")
        sys.exit(1)

    login_resp = client.post("/accounts/login/", {
        "username": username,
        "password": password,
        "branch": branch.code,
    })
    print("Login status:", login_resp.status_code, "redirect->", getattr(login_resp, "url", None))

    urls = [
        "/",
        "/catalog/",
        "/pos/",
        "/orders/",
        "/orders/kanban/",
        "/orders/pickup/",
        "/orders/delivery/",
        "/payments/",
        "/reports/",
        "/reports/z-report/",
        "/settings/",
        "/management/",
        "/management/branches/",
        "/management/staff/",
        "/management/audit/",
        "/settings/whatsapp/",
    ]

    for url in urls:
        resp = client.get(url)
        status = resp.status_code
        redirect_to = resp.url if status in (301, 302) else None
        print(f"GET {url} -> {status} {redirect_to or ''}")

    api_urls = [
        "/orders/api/customer-search/?q=a",
        "/orders/api/customer-lookup/?phone=123",
        "/catalog/api/pos-data/",
    ]
    for url in api_urls:
        resp = client.get(url)
        status = resp.status_code
        print(f"GET {url} -> {status}")
