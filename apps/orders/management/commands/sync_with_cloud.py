from __future__ import annotations

import requests

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone

from apps.core.models import SyncState
from apps.settings_app.utils import get_sync_settings
from apps.orders.models import Customer, Order
from apps.orders.sync_utils import apply_customer_payload, apply_order_payload, parse_dt, serialize_customer, serialize_order


class Command(BaseCommand):
    help = "Sync local data with the cloud backend (hybrid mode)."

    def handle(self, *args, **options):
        sync_settings = get_sync_settings()
        enabled = settings.SYNC_ENABLED
        base_url = settings.CLOUD_BASE_URL
        api_token = settings.SYNC_API_TOKEN
        if sync_settings:
            enabled = sync_settings.enabled
            base_url = sync_settings.cloud_base_url or base_url
            api_token = sync_settings.api_token or api_token

        if not enabled:
            self.stdout.write("Sync disabled.")
            raise SystemExit(3)
        if not base_url or not api_token:
            self.stdout.write("Missing CLOUD_BASE_URL or SYNC_API_TOKEN.")
            raise SystemExit(3)

        base_url = base_url.rstrip("/")
        push_url = f"{base_url}/orders/sync/push/"
        pull_url = f"{base_url}/orders/sync/pull/"
        headers = {"X-Sync-Token": api_token}

        state, _ = SyncState.objects.get_or_create(key="cloud")
        last_synced_at = state.last_synced_at

        customers_qs = Customer.objects.all().order_by("id")
        orders_qs = Order.objects.select_related("customer").prefetch_related("items").order_by("id")

        customers_to_sync = customers_qs.filter(
            models.Q(cloud_synced_at__isnull=True)
            | models.Q(updated_at__gt=models.F("cloud_synced_at"))
        )
        orders_to_sync = orders_qs.filter(
            models.Q(cloud_synced_at__isnull=True)
            | models.Q(updated_at__gt=models.F("cloud_synced_at"))
        )

        customers_to_sync = list(customers_to_sync[:500])
        orders_to_sync = list(orders_to_sync[:300])

        if customers_to_sync or orders_to_sync:
            payload = {
                "customers": [serialize_customer(c) for c in customers_to_sync],
                "orders": [serialize_order(o) for o in orders_to_sync],
            }
            try:
                res = requests.post(push_url, json=payload, headers=headers, timeout=20)
                res.raise_for_status()
                now = timezone.now()
                if customers_to_sync:
                    Customer.objects.filter(id__in=[c.id for c in customers_to_sync]).update(cloud_synced_at=now)
                if orders_to_sync:
                    Order.objects.filter(id__in=[o.id for o in orders_to_sync]).update(cloud_synced_at=now)
                self.stdout.write(f"Pushed {len(customers_to_sync)} customers and {len(orders_to_sync)} orders.")
            except Exception as exc:
                self.stdout.write(f"Push failed: {exc}")
                return
        else:
            self.stdout.write("No local changes to push.")

        params = {}
        if last_synced_at:
            params["since"] = last_synced_at.isoformat()
        try:
            res = requests.get(pull_url, headers=headers, params=params, timeout=20)
            res.raise_for_status()
            data = res.json()
        except Exception as exc:
            self.stdout.write(f"Pull failed: {exc}")
            return

        applied_customers = 0
        applied_orders = 0

        for customer_payload in data.get("customers", []) or []:
            if not isinstance(customer_payload, dict):
                continue
            _, updated = apply_customer_payload(customer_payload)
            if updated:
                applied_customers += 1

        for order_payload in data.get("orders", []) or []:
            if not isinstance(order_payload, dict):
                continue
            _, updated = apply_order_payload(order_payload)
            if updated:
                applied_orders += 1

        server_time = parse_dt(data.get("server_time")) or timezone.now()
        state.last_synced_at = server_time
        state.save(update_fields=["last_synced_at"])

        self.stdout.write(f"Pulled {applied_customers} customers and {applied_orders} orders.")
