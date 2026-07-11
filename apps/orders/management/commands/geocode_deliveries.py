import time
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.orders.models import Order


class Command(BaseCommand):
    help = "Geocode delivery addresses using Google Maps API."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="Max orders to geocode.")
        parser.add_argument("--sleep", type=float, default=0.1, help="Sleep between calls.")

    def handle(self, *args, **options):
        api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "")
        if not api_key:
            self.stdout.write(self.style.ERROR("GOOGLE_MAPS_API_KEY is not set."))
            return

        limit = options["limit"]
        delay = options["sleep"]

        qs = Order.objects.filter(delivery_required=True, delivery_address__gt="").order_by("-created_at")
        qs = qs.filter(delivery_lat__isnull=True)[:limit]

        count = 0
        for o in qs:
            addr = o.delivery_address
            if not addr:
                continue
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": addr, "key": api_key}
            res = requests.get(url, params=params, timeout=15)
            if res.status_code >= 400:
                continue
            data = res.json()
            if data.get("status") != "OK":
                continue
            loc = data["results"][0]["geometry"]["location"]
            o.delivery_lat = loc.get("lat")
            o.delivery_lng = loc.get("lng")
            o.save(update_fields=["delivery_lat", "delivery_lng", "updated_at"])
            count += 1
            time.sleep(delay)

        self.stdout.write(self.style.SUCCESS(f"Geocoded {count} deliveries."))
