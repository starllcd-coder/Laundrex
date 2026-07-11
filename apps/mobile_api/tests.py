import json

from django.test import TestCase, override_settings


class OtpSecurityTests(TestCase):
    @override_settings(OTP_DEBUG_RETURN_CODE=False)
    def test_otp_code_is_not_returned_by_default(self):
        response = self.client.post(
            "/api/auth/otp/send",
            data=json.dumps({"phone": "+96890000000", "purpose": "login"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("debug_code", response.json())

    @override_settings(OTP_DEBUG_RETURN_CODE=False)
    def test_forgot_password_does_not_disclose_missing_account(self):
        response = self.client.post(
            "/api/auth/forgot-password",
            data=json.dumps({"phone": "+96891111111"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "expires_in": 300})
