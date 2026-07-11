import os
import sys
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = os.getenv("LAUNDREX_E2E_BASE", "http://127.0.0.1:8000").rstrip("/")
USER = os.getenv("LAUNDREX_E2E_USER", "").strip()
PASS = os.getenv("LAUNDREX_E2E_PASS", "")

if not USER or not PASS:
    print("Missing credentials. Set LAUNDREX_E2E_USER and LAUNDREX_E2E_PASS.")
    sys.exit(1)

PAGES = [
    ("/", "Overview"),
    ("/catalog/", "Items, Services, Prices & Barcodes"),
    ("/pos/", "New Order"),
    ("/orders/", "Orders"),
    ("/orders/kanban/", "Orders Kanban"),
    ("/orders/pickup/", "Pickup Counter"),
    ("/orders/delivery/", "Delivery"),
    ("/payments/", "Payments"),
    ("/reports/", "Reports"),
    ("/reports/z-report/", "Z Report"),
    ("/settings/", "Settings"),
    ("/management/", "Management"),
    ("/management/branches/", "Branches"),
    ("/management/staff/", "Staff"),
    ("/management/audit/", "Audit Logs"),
    ("/settings/whatsapp/", "WhatsApp"),
]

MARKER = os.getenv("LAUNDREX_E2E_MARKER", "").strip() or f"E2E-{int(time.time())}"
PURGE_ALL_E2E = os.getenv("LAUNDREX_E2E_PURGE", "").strip() == "1"


def select_first_branch(page):
    options = page.locator("select#branch option")
    count = options.count()
    for i in range(count):
        value = options.nth(i).get_attribute("value")
        if value:
            page.select_option("select#branch", value)
            return True
    return False


def cleanup_test_data(marker):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "laundrex.settings")
    try:
        import django
        django.setup()
    except Exception as exc:
        print("Cleanup skipped (Django setup failed):", exc)
        return

    from apps.orders.models import Order, OrderItem, OrderStatusLog, Customer
    from apps.payments.models import Payment
    from apps.settings_app.models import WhatsAppMessageLog
    from apps.management.models import Branch

    if PURGE_ALL_E2E:
        orders = Order.objects.filter(notes__icontains="E2E-")
    else:
        orders = Order.objects.filter(notes__icontains=marker)
    Payment.objects.filter(order__in=orders).delete()
    OrderItem.objects.filter(order__in=orders).delete()
    OrderStatusLog.objects.filter(order__in=orders).delete()
    WhatsAppMessageLog.objects.filter(order__in=orders).delete()
    orders.delete()

    if PURGE_ALL_E2E:
        Customer.objects.filter(phone__startswith="E2E-").delete()
        Branch.objects.filter(code__startswith="e2e-").delete()
    else:
        Customer.objects.filter(phone__startswith=marker).delete()
        Branch.objects.filter(code__startswith=marker.lower()).delete()


def main():
    failures = []
    created_order_no = ""
    print("E2E marker:", MARKER)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(f"{BASE_URL}/accounts/login/", wait_until="networkidle")
        page.fill("#username", USER)
        page.fill("#password", PASS)
        if not select_first_branch(page):
            failures.append("No branch option available on login form.")
        page.click("#loginBtn")

        try:
            page.wait_for_url(f"{BASE_URL}/", timeout=10000)
        except PlaywrightTimeoutError:
            failures.append("Login did not redirect to dashboard.")

        for path, heading in PAGES:
            url = f"{BASE_URL}{path}"
            page.goto(url, wait_until="networkidle")
            if "/accounts/login" in page.url:
                failures.append(f"Auth redirect on {path}")
                continue
            try:
                page.locator("h1", has_text=heading).first.wait_for(timeout=5000)
            except PlaywrightTimeoutError:
                failures.append(f"Missing heading '{heading}' on {path}")

        # Deep checks: Catalog seed defaults
        page.goto(f"{BASE_URL}/catalog/", wait_until="networkidle")
        try:
            page.locator("button", has_text="Seed Defaults").first.wait_for(timeout=5000)
            page.click("button:has-text('Seed Defaults')")
            page.wait_for_url(f"{BASE_URL}/catalog/", timeout=10000)
        except PlaywrightTimeoutError:
            failures.append("Seed Defaults button not found or seed failed.")

        # Deep checks: POS add item + Save & Print + save order
        page.goto(f"{BASE_URL}/pos/", wait_until="networkidle")
        try:
            page.wait_for_selector("#itemSelect", timeout=10000)
            page.wait_for_selector("#serviceSelect", timeout=10000)

            # Wait for items to load
            page.wait_for_function("document.querySelector('#itemSelect').options.length > 1", timeout=10000)

            # Customer info + notes for cleanup
            page.fill("#custName", f"E2E Test {MARKER}")
            page.fill("#custPhone", f"{MARKER}01")
            page.fill("#notes", f"{MARKER} - auto test order")

            # Select first available item
            item_options = page.locator("#itemSelect option")
            item_count = item_options.count()
            if item_count > 1:
                item_value = item_options.nth(1).get_attribute("value")
                page.select_option("#itemSelect", item_value)
            else:
                failures.append("No items available in POS item list.")

            # Select first available service
            service_options = page.locator("#serviceSelect option")
            service_count = service_options.count()
            if service_count > 0:
                service_value = service_options.nth(0).get_attribute("value")
                page.select_option("#serviceSelect", service_value)
            else:
                failures.append("No services available in POS service list.")

            page.fill("#qty", "1")

            # Add item to order
            page.click("#addBtn")
            page.wait_for_function("document.querySelectorAll('#itemsTable tbody tr').length > 0", timeout=10000)

            # Save & Print (creates order, opens receipt in new tab)
            with page.expect_response(lambda r: "/pos/api/create-order/" in r.url) as resp_info:
                with page.expect_popup() as pop:
                    page.click("#printBtn")
            resp = resp_info.value
            try:
                data = resp.json()
                created_order_no = str(data.get("order_no", "") or "")
            except Exception:
                created_order_no = ""
            if not created_order_no:
                failures.append("Create-order did not return order number.")

            receipt = pop.value
            receipt.wait_for_load_state("domcontentloaded")
            if "receipt" not in receipt.url:
                failures.append("Receipt window did not open as expected.")
            receipt.close()
        except PlaywrightTimeoutError:
            failures.append("POS flow failed (add item or Save & Print).")

        # Orders list: Next status button (requires permission)
        if created_order_no:
            page.goto(f"{BASE_URL}/orders/", wait_until="networkidle")
            try:
                row = page.locator("tr", has_text=f"#{created_order_no}").first
                row.locator("button", has_text="Next").click()
                page.wait_for_load_state("networkidle")
            except PlaywrightTimeoutError:
                failures.append("Orders list Next status action failed.")

            # Order detail: Mark Urgent + Move status
            page.goto(f"{BASE_URL}/orders/{created_order_no}/", wait_until="networkidle")
            try:
                urgent_btn = page.locator("button", has_text="Mark Urgent")
                if urgent_btn.count() > 0:
                    urgent_btn.first.click()
                    page.wait_for_load_state("networkidle")
                clear_btn = page.locator("button", has_text="Clear Urgent")
                if clear_btn.count() > 0:
                    clear_btn.first.click()
                    page.wait_for_load_state("networkidle")
                page.wait_for_load_state("networkidle")
                page.locator("button", has_text="Move to").first.click()
                page.wait_for_load_state("networkidle")
            except PlaywrightTimeoutError:
                failures.append("Order detail actions failed (urgent/move).")

            # Pickup counter lookup and mark ready/delivered
            page.goto(f"{BASE_URL}/orders/pickup/", wait_until="networkidle")
            try:
                page.fill("input[name='lookup_code']", created_order_no)
                page.click("button:has-text('Lookup')")
                page.wait_for_load_state("networkidle")
                page.click("button:has-text('Mark Ready')")
                page.wait_for_load_state("networkidle")
                page.click("button:has-text('Mark Delivered')")
                page.wait_for_load_state("networkidle")
            except PlaywrightTimeoutError:
                failures.append("Pickup counter actions failed.")

            # Delivery detail: set required + save
            page.goto(f"{BASE_URL}/orders/delivery/{created_order_no}/", wait_until="networkidle")
            try:
                page.select_option("select[name='delivery_required']", "1")
                page.fill("input[name='delivery_address']", f"{MARKER} Address")
                page.fill("input[name='delivery_phone']", f"{MARKER}99")
                page.fill("input[name='delivery_slot']", "Today 4-6 PM")
                page.fill("input[name='delivery_fee']", "0.500")
                page.fill("input[name='delivery_driver_name']", "E2E Driver")
                page.fill("input[name='delivery_driver_phone']", f"{MARKER}77")
                page.click("button:has-text('Save Delivery')")
                page.wait_for_load_state("networkidle")
            except PlaywrightTimeoutError:
                failures.append("Delivery detail save failed.")

            # Payments detail: add payment
            page.goto(f"{BASE_URL}/payments/order/{created_order_no}/", wait_until="networkidle")
            try:
                page.fill("input[name='amount']", "1.000")
                page.fill("input[name='reference']", MARKER)
                page.fill("input[name='note']", "E2E payment")
                page.click("button:has-text('Add Payment')")
                page.wait_for_load_state("networkidle")
            except PlaywrightTimeoutError:
                failures.append("Payment add failed.")

        # Management: add a branch then return
        page.goto(f"{BASE_URL}/management/branches/", wait_until="networkidle")
        try:
            marker_code = MARKER.lower()
            page.fill("input[name='code']", marker_code)
            page.fill("input[name='name']", f"{MARKER} Branch")
            page.click("button:has-text('Add')")
            page.wait_for_load_state("networkidle")
        except PlaywrightTimeoutError:
            failures.append("Branch add failed.")

        browser.close()

    cleanup_test_data(MARKER)

    if failures:
        print("E2E FAILURES:")
        for f in failures:
            print("-", f)
        sys.exit(1)

    print("E2E OK: all pages loaded and headings found.")


if __name__ == "__main__":
    main()
