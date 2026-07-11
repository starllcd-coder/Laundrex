from django.contrib import admin

from .models import Customer, Order, OrderItem, OrderStatusLog


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
	list_display = ("id", "name", "phone", "vip", "points", "vip_discount_percent")
	search_fields = ("name", "phone")
	list_filter = ("vip",)
	inlines = []


class OrderItemInline(admin.TabularInline):
	model = OrderItem
	extra = 0


class OrderStatusLogInline(admin.TabularInline):
	model = OrderStatusLog
	extra = 0
	readonly_fields = ("created_at",)
	ordering = ("-created_at",)


class CustomerOrderInline(admin.TabularInline):
	model = Order
	extra = 0
	readonly_fields = ("order_no", "status", "total", "created_at")
	fields = ("order_no", "status", "total", "created_at")
	can_delete = False


CustomerAdmin.inlines = [CustomerOrderInline]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ("order_no", "branch", "customer", "status", "delivery_status", "urgent", "total", "paid", "balance", "created_at")
	list_filter = ("status", "delivery_status", "branch", "urgent")
	search_fields = ("order_no", "customer__name", "customer__phone")
	inlines = [OrderItemInline, OrderStatusLogInline]
	actions = [
		"mark_urgent",
		"mark_accepted",
		"mark_pickup_assigned",
		"mark_out_for_delivery",
		"resend_status_notification",
	]

	@admin.action(description="Mark selected orders as urgent")
	def mark_urgent(self, request, queryset):
		queryset.update(urgent=True)

	def _bulk_set_status(self, request, queryset, to_status, note):
		for order in queryset:
			if order.status == to_status:
				continue
			from_status = order.status
			order.status = to_status
			fields = ["status", "updated_at"]
			if to_status == Order.Status.PICKUP_ASSIGNED:
				order.delivery_status = Order.DeliveryStatus.ASSIGNED
				fields.append("delivery_status")
			elif to_status == Order.Status.OUT_FOR_DELIVERY:
				order.delivery_status = Order.DeliveryStatus.OUT
				fields.append("delivery_status")
			elif to_status == Order.Status.DELIVERED:
				order.delivery_status = Order.DeliveryStatus.DELIVERED
				fields.append("delivery_status")
			order.save(update_fields=fields)
			OrderStatusLog.objects.create(
				order=order,
				from_status=from_status,
				to_status=to_status,
				note=note,
				created_by=request.user,
			)
			try:
				from apps.mobile_api.models import MobileNotification
				if order.customer_id:
					MobileNotification.objects.create(
						customer=order.customer,
						order=order,
						title="Order update",
						message=f"Order #{order.order_no} is now {order.get_status_display()}.",
						event_code="status_change",
					)
			except Exception:
				pass

	@admin.action(description="Set status: Accepted")
	def mark_accepted(self, request, queryset):
		self._bulk_set_status(request, queryset, Order.Status.ACCEPTED, "Accepted by laundry")

	@admin.action(description="Set status: Pickup Assigned")
	def mark_pickup_assigned(self, request, queryset):
		self._bulk_set_status(request, queryset, Order.Status.PICKUP_ASSIGNED, "Pickup assigned")

	@admin.action(description="Set status: Out for Delivery")
	def mark_out_for_delivery(self, request, queryset):
		self._bulk_set_status(request, queryset, Order.Status.OUT_FOR_DELIVERY, "Out for delivery")

	@admin.action(description="Resend status notification (log only)")
	def resend_status_notification(self, request, queryset):
		for order in queryset:
			OrderStatusLog.objects.create(
				order=order,
				from_status=order.status,
				to_status=order.status,
				note="Resend notification requested",
				created_by=request.user,
			)


@admin.register(OrderStatusLog)
class OrderStatusLogAdmin(admin.ModelAdmin):
	list_display = ("order", "from_status", "to_status", "created_by", "created_at")
	list_filter = ("to_status",)
