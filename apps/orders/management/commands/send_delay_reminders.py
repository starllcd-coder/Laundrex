from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.management.models import Branch
from apps.orders.models import Order
from apps.settings_app.models import WhatsAppMessageLog
from apps.settings_app.utils import send_whatsapp_message_auto


class Command(BaseCommand):
    help = "Send pickup delay reminders for READY orders."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=2, help="Send reminders for orders older than N days.")
        parser.add_argument("--template", default="pickup_reminder", help="WhatsApp template key.")
        parser.add_argument("--limit", type=int, default=200, help="Max orders to process.")

    def handle(self, *args, **options):
        days = options["days"]
        template_key = options["template"]
        limit = options["limit"]

        cutoff = timezone.now() - timedelta(days=days)
        qs = Order.objects.select_related("customer").filter(
            status=Order.Status.READY,
            created_at__lte=cutoff,
        ).order_by("created_at")

        sent = 0
        skipped = 0
        for order in qs[:limit]:
            if not order.customer:
                skipped += 1
                continue

            recent = WhatsAppMessageLog.objects.filter(
                order=order,
                template_key=template_key,
                created_at__gte=timezone.now() - timedelta(hours=24),
            )
            if recent.exists():
                skipped += 1
                continue

            branch_obj = Branch.objects.filter(code=order.branch).first()
            branch_name = branch_obj.name if branch_obj else order.branch
            lang = order.customer.preferred_language if order.customer.preferred_language in ("en", "ar") else "en"
            ok, _ = send_whatsapp_message_auto(order, order.customer, branch_name, template_key, lang)
            if ok:
                sent += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Reminders sent: {sent}. Skipped: {skipped}."))
