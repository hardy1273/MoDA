"""Hosted Checkout session creation, confirmation, and webhook verification.

The simulated provider is exercised here; the Stripe paths are covered by
their error handling (an unreachable/unconfigured Stripe must never raise
into a request handler).
"""

import pytest
from pydantic import ValidationError

from app.payments import (
    CheckoutLine,
    create_checkout_session,
    retrieve_checkout_session,
    verify_webhook,
)
from app.schemas import CheckoutOut, ConfirmIn

LINES = [
    CheckoutLine(name="Ivory sweater", image_url="https://x/i.jpg", unit_amount_cents=14_800, qty=1),
    CheckoutLine(name="Navy jeans", image_url="https://x/j.jpg", unit_amount_cents=10_899, qty=2),
]


class TestCreateCheckoutSession:
    def test_simulated_session_has_id_but_no_url(self):
        r = create_checkout_session(LINES, "https://a/ok", "https://a/no")
        assert r.ok and r.simulated
        assert r.session_id.startswith("cs_mock")
        assert r.url is None  # nothing to redirect to

    def test_empty_cart_rejected(self):
        r = create_checkout_session([], "https://a/ok", "https://a/no")
        assert not r.ok and "empty" in r.message.lower()

    def test_session_ids_are_unique(self):
        a = create_checkout_session(LINES, "https://a/ok", "https://a/no")
        b = create_checkout_session(LINES, "https://a/ok", "https://a/no")
        assert a.session_id != b.session_id


class TestRetrieveCheckoutSession:
    def test_simulated_session_reports_paid(self):
        s = retrieve_checkout_session("cs_mock_abc")
        assert s.ok and s.paid
        assert s.payment_ref == "cs_mock_abc"


class TestWebhookVerification:
    def test_rejected_without_a_configured_secret(self):
        # No STRIPE_WEBHOOK_SECRET set -> never trust the payload
        assert verify_webhook(b'{"type":"checkout.session.completed"}', "sig") is None

    def test_rejected_with_garbage_signature(self):
        assert verify_webhook(b"{}", "t=1,v1=deadbeef") is None


class TestCheckoutSchemas:
    def test_redirect_mode_carries_url(self):
        c = CheckoutOut(mode="redirect", url="https://checkout.stripe.com/c/pay/x")
        assert c.order is None and c.url.startswith("https://")

    def test_simulated_mode_carries_no_url(self):
        assert CheckoutOut(mode="simulated").url is None

    def test_confirm_requires_a_session_id(self):
        assert ConfirmIn(session_id="cs_test_123").session_id == "cs_test_123"

    @pytest.mark.parametrize("bad", ["", "ab"])
    def test_confirm_rejects_short_ids(self, bad):
        with pytest.raises(ValidationError):
            ConfirmIn(session_id=bad)
