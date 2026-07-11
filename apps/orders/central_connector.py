from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from urllib import request

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


def _connector_headers(body: bytes) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Connector-Secret": str(getattr(settings, "CENTRAL_CONNECTOR_SECRET", "") or ""),
    }
    if getattr(settings, "CENTRAL_CONNECTOR_SIGNED", False):
        ts = str(int(time.time()))
        nonce = uuid.uuid4().hex
        secret = str(getattr(settings, "CENTRAL_CONNECTOR_SECRET", "") or "").encode("utf-8")
        msg = f"{ts}.{nonce}.".encode("utf-8") + body
        sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()
        headers["X-Connector-Timestamp"] = ts
        headers["X-Connector-Nonce"] = nonce
        headers["X-Connector-Signature"] = sig
    return headers


def post_connector(path: str, payload: dict) -> dict:
    base = str(getattr(settings, "CENTRAL_PLATFORM_URL", "http://127.0.0.1:8000")).rstrip("/")
    url = f"{base}/api/connectors/{path.lstrip('/')}"
    body = json.dumps(payload, default=str).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    for key, value in _connector_headers(body).items():
        if value:
            req.add_header(key, value)
    with request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw)


def verify_central_request(request) -> tuple[bool, str]:
    secret = str(getattr(settings, "CENTRAL_CONNECTOR_SECRET", "") or "")
    if not secret or not hmac.compare_digest(request.headers.get("X-Connector-Secret", ""), secret):
        return False, "Unauthorized"
    expected_tenant = str(getattr(settings, "CENTRAL_TENANT_CODE", "") or "").strip()
    if expected_tenant and request.headers.get("X-Tenant-Code", "").strip() != expected_tenant:
        return False, "Tenant mismatch"
    if not getattr(settings, "CENTRAL_CONNECTOR_SIGNED", False):
        return True, ""
    timestamp = request.headers.get("X-Connector-Timestamp", "").strip()
    nonce = request.headers.get("X-Connector-Nonce", "").strip()
    signature = request.headers.get("X-Connector-Signature", "").strip()
    if not timestamp or not nonce or not signature:
        return False, "Missing signature headers"
    try:
        age = abs(int(time.time()) - int(timestamp))
    except ValueError:
        return False, "Invalid connector timestamp"
    if age > int(getattr(settings, "CENTRAL_CONNECTOR_MAX_SKEW_SECONDS", 300)):
        return False, "Expired connector request"
    expected = hmac.new(secret.encode("utf-8"), f"{timestamp}.{nonce}.".encode("utf-8") + request.body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False, "Invalid connector signature"
    if not cache.add(f"central-connector-nonce:{nonce}", timezone.now().isoformat(), timeout=600):
        return False, "Connector replay detected"
    return True, ""
