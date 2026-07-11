import hashlib
import hmac
import time

from django.test import RequestFactory, SimpleTestCase, override_settings

from .central_connector import verify_central_request


@override_settings(CENTRAL_CONNECTOR_SECRET="strong-provider-test-secret", CENTRAL_CONNECTOR_SIGNED=True, CENTRAL_TENANT_CODE="LNX-ONE")
class CentralConnectorSecurityTests(SimpleTestCase):
    def test_signature_and_tenant_are_required(self):
        body = b'{"booking_id":"NXV-1"}'
        timestamp = str(int(time.time()))
        nonce = "laundry-nonce"
        signature = hmac.new(b"strong-provider-test-secret", f"{timestamp}.{nonce}.".encode() + body, hashlib.sha256).hexdigest()
        request = RequestFactory().generic(
            "POST", "/orders/central/webhook/", body, content_type="application/json",
            HTTP_X_CONNECTOR_SECRET="strong-provider-test-secret",
            HTTP_X_CONNECTOR_TIMESTAMP=timestamp,
            HTTP_X_CONNECTOR_NONCE=nonce,
            HTTP_X_CONNECTOR_SIGNATURE=signature,
            HTTP_X_TENANT_CODE="LNX-ONE",
        )
        self.assertEqual(verify_central_request(request), (True, ""))
        self.assertEqual(verify_central_request(request)[0], False)
