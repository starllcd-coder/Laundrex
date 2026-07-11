from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Dict, Tuple

from django.utils import timezone

from apps.core.models import ErrorLog
from .models import Customer, Order, OrderItem


def parse_dt(value: str | None):
    if not value:
        return None
    try:
        dt = timezone.datetime.fromisoformat(value)
    except Exception:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def parse_date(value: str | None):
    if not value:
        return None
    try:
        return timezone.datetime.fromisoformat(value).date()
    except Exception:
        try:
            return timezone.datetime.strptime(value, "%Y-%m-%d").date()
        except Exception:
            return None


def _clean_str(value: Any) -> str:
    return (value or "").strip()


def serialize_customer(customer: Customer) -> Dict[str, Any]:
    return {
        "sync_uid": customer.sync_uid,
        "name": customer.name,
        "phone": customer.phone,
        "vip": customer.vip,
        "notes": customer.notes,
        "address": customer.address,
        "address2": customer.address2,
        "points": customer.points,
        "vip_discount_percent": str(customer.vip_discount_percent),
        "preferred_language": customer.preferred_language,
        "whatsapp_opt_in": customer.whatsapp_opt_in,
        "whatsapp_number": customer.whatsapp_number,
        "whatsapp_opt_in_at": customer.whatsapp_opt_in_at.isoformat() if customer.whatsapp_opt_in_at else None,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
    }


def serialize_order(order: Order) -> Dict[str, Any]:
    items = []
    for item in order.items.all().order_by("id"):
        items.append(
            {
                "item_name": item.item_name,
                "service_name": item.service_name,
                "qty": item.qty,
                "price": str(item.price),
                "line_total": str(item.line_total),
            }
        )

    return {
        "order_no": order.order_no,
        "pickup_token": order.pickup_token,
        "branch": order.branch,
        "status": order.status,
        "urgent": order.urgent,
        "subtotal": str(order.subtotal),
        "discount": str(order.discount),
        "tax": str(order.tax),
        "total": str(order.total),
        "paid": str(order.paid),
        "balance": str(order.balance),
        "points_awarded": order.points_awarded,
        "loyalty_points_awarded": order.loyalty_points_awarded,
        "points_redeemed": order.points_redeemed,
        "points_redeemed_value": str(order.points_redeemed_value),
        "delivery_required": order.delivery_required,
        "delivery_status": order.delivery_status,
        "delivery_address": order.delivery_address,
        "delivery_zone": order.delivery_zone,
        "delivery_phone": order.delivery_phone,
        "delivery_lat": order.delivery_lat,
        "delivery_lng": order.delivery_lng,
        "delivery_slot": order.delivery_slot,
        "delivery_fee": str(order.delivery_fee),
        "delivery_driver_name": order.delivery_driver_name,
        "delivery_driver_phone": order.delivery_driver_phone,
        "delivery_notes": order.delivery_notes,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "estimated_ready_at": order.estimated_ready_at.isoformat() if order.estimated_ready_at else None,
        "pickup_date": order.pickup_date.isoformat() if order.pickup_date else None,
        "pickup_slot": order.pickup_slot,
        "pickup_notes": order.pickup_notes,
        "notes": order.notes,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "customer": serialize_customer(order.customer) if order.customer else None,
        "items": items,
    }


def apply_customer_payload(payload: Dict[str, Any]) -> Tuple[Customer, bool]:
    phone = _clean_str(payload.get("phone"))
    sync_uid = _clean_str(payload.get("sync_uid"))
    customer = None
    if phone:
        customer = Customer.objects.filter(phone=phone).first()
    if not customer and sync_uid:
        customer = Customer.objects.filter(sync_uid=sync_uid).first()

    payload_updated_at = parse_dt(payload.get("updated_at"))
    payload_created_at = parse_dt(payload.get("created_at"))

    fields = {
        "name": _clean_str(payload.get("name")),
        "phone": phone,
        "vip": bool(payload.get("vip")),
        "notes": _clean_str(payload.get("notes")),
        "address": _clean_str(payload.get("address")),
        "address2": _clean_str(payload.get("address2")),
        "points": int(payload.get("points") or 0),
        "vip_discount_percent": Decimal(str(payload.get("vip_discount_percent") or "0")),
        "preferred_language": _clean_str(payload.get("preferred_language") or "en")[:2],
        "whatsapp_opt_in": bool(payload.get("whatsapp_opt_in")),
        "whatsapp_number": _clean_str(payload.get("whatsapp_number")),
        "whatsapp_opt_in_at": parse_dt(payload.get("whatsapp_opt_in_at")),
    }

    if customer:
        if payload_updated_at and customer.updated_at and customer.updated_at >= payload_updated_at:
            ErrorLog.objects.create(
                level="WARNING",
                message=f"Sync skipped customer {customer.id} (local newer).",
                path="sync/customer",
                method="SYNC",
            )
            return customer, False
        update_fields = dict(fields)
        if payload_updated_at:
            update_fields["updated_at"] = payload_updated_at
        if payload_created_at:
            update_fields["created_at"] = payload_created_at
        if sync_uid and customer.sync_uid != sync_uid:
            update_fields["sync_uid"] = sync_uid
        Customer.objects.filter(id=customer.id).update(**update_fields)
        customer.refresh_from_db()
        return customer, True

    if not sync_uid:
        sync_uid = str(uuid.uuid4())

    customer = Customer.objects.create(sync_uid=sync_uid, **fields)
    update_fields = {}
    if payload_created_at:
        update_fields["created_at"] = payload_created_at
    if payload_updated_at:
        update_fields["updated_at"] = payload_updated_at
    if update_fields:
        Customer.objects.filter(id=customer.id).update(**update_fields)
        customer.refresh_from_db()
    return customer, True


def apply_order_payload(payload: Dict[str, Any]) -> Tuple[Order | None, bool]:
    order_no = _clean_str(payload.get("order_no"))
    if not order_no:
        return None, False

    customer_payload = payload.get("customer") or {}
    customer = None
    if isinstance(customer_payload, dict) and customer_payload:
        customer, _ = apply_customer_payload(customer_payload)

    order = Order.objects.filter(order_no=order_no).first()
    payload_updated_at = parse_dt(payload.get("updated_at"))
    payload_created_at = parse_dt(payload.get("created_at"))

    pickup_token = _clean_str(payload.get("pickup_token"))
    fields = {
        "branch": _clean_str(payload.get("branch")) or "muscat",
        "status": _clean_str(payload.get("status")) or Order.Status.RECEIVED,
        "urgent": bool(payload.get("urgent")),
        "customer": customer,
        "subtotal": Decimal(str(payload.get("subtotal") or "0")),
        "discount": Decimal(str(payload.get("discount") or "0")),
        "tax": Decimal(str(payload.get("tax") or "0")),
        "total": Decimal(str(payload.get("total") or "0")),
        "paid": Decimal(str(payload.get("paid") or "0")),
        "balance": Decimal(str(payload.get("balance") or "0")),
        "points_awarded": bool(payload.get("points_awarded")),
        "loyalty_points_awarded": int(payload.get("loyalty_points_awarded") or 0),
        "points_redeemed": int(payload.get("points_redeemed") or 0),
        "points_redeemed_value": Decimal(str(payload.get("points_redeemed_value") or "0")),
        "delivery_required": bool(payload.get("delivery_required")),
        "delivery_status": _clean_str(payload.get("delivery_status")) or Order.DeliveryStatus.PENDING,
        "delivery_address": _clean_str(payload.get("delivery_address")),
        "delivery_zone": _clean_str(payload.get("delivery_zone")),
        "delivery_phone": _clean_str(payload.get("delivery_phone")),
        "delivery_lat": payload.get("delivery_lat"),
        "delivery_lng": payload.get("delivery_lng"),
        "delivery_slot": _clean_str(payload.get("delivery_slot")),
        "delivery_fee": Decimal(str(payload.get("delivery_fee") or "0")),
        "delivery_driver_name": _clean_str(payload.get("delivery_driver_name")),
        "delivery_driver_phone": _clean_str(payload.get("delivery_driver_phone")),
        "delivery_notes": _clean_str(payload.get("delivery_notes")),
        "delivered_at": parse_dt(payload.get("delivered_at")),
        "estimated_ready_at": parse_dt(payload.get("estimated_ready_at")),
        "pickup_date": parse_date(payload.get("pickup_date")),
        "pickup_slot": _clean_str(payload.get("pickup_slot")),
        "pickup_notes": _clean_str(payload.get("pickup_notes")),
        "notes": _clean_str(payload.get("notes")),
    }
    if pickup_token:
        fields["pickup_token"] = pickup_token

    if order:
        if payload_updated_at and order.updated_at and order.updated_at >= payload_updated_at:
            ErrorLog.objects.create(
                level="WARNING",
                message=f"Sync skipped order {order.order_no} (local newer).",
                path="sync/order",
                method="SYNC",
                branch_code=order.branch,
            )
            return order, False
        update_fields = dict(fields)
        if payload_updated_at:
            update_fields["updated_at"] = payload_updated_at
        if payload_created_at:
            update_fields["created_at"] = payload_created_at
        Order.objects.filter(id=order.id).update(**update_fields)
        order.refresh_from_db()
    else:
        order = Order.objects.create(order_no=order_no, **fields)
        update_fields = {}
        if payload_created_at:
            update_fields["created_at"] = payload_created_at
        if payload_updated_at:
            update_fields["updated_at"] = payload_updated_at
        if update_fields:
            Order.objects.filter(id=order.id).update(**update_fields)
            order.refresh_from_db()

    items_payload = payload.get("items") or []
    if isinstance(items_payload, list):
        OrderItem.objects.filter(order=order).delete()
        items = []
        for item in items_payload:
            if not isinstance(item, dict):
                continue
            qty = int(item.get("qty") or 1)
            price = Decimal(str(item.get("price") or "0"))
            line_total = Decimal(str(item.get("line_total") or (qty * price)))
            items.append(
                OrderItem(
                    order=order,
                    item_name=_clean_str(item.get("item_name")),
                    service_name=_clean_str(item.get("service_name")),
                    qty=qty,
                    price=price,
                    line_total=line_total,
                )
            )
        if items:
            OrderItem.objects.bulk_create(items)

    return order, True
