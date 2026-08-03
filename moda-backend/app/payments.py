"""Payment + payout provider abstraction.

Two providers, selected automatically by whether STRIPE_SECRET_KEY is set:

  mock    — everything succeeds and returns a synthetic reference. Lets the
            full marketplace flow (onboarding, checkout, payouts) be
            exercised end to end with no Stripe account.
  stripe  — real Stripe Connect (Express accounts, separate charges and
            transfers). Only the payout side is wired; see `charge()`.

Callers never branch on the provider: they call these functions and read
`.simulated` if they need to tell the user nothing real happened.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class PaymentResult:
    ok: bool
    provider: str
    ref: str
    simulated: bool = False
    message: str = ""


@dataclass(frozen=True)
class AccountResult:
    ok: bool
    provider: str
    account_id: str
    simulated: bool = False
    message: str = ""


@dataclass(frozen=True)
class OnboardingResult:
    """`url` is None in mock mode — there's nothing to visit."""

    ok: bool
    provider: str
    url: str | None
    simulated: bool = False
    message: str = ""


@dataclass(frozen=True)
class TransferResult:
    ok: bool
    provider: str
    ref: str
    simulated: bool = False
    message: str = ""


def active_provider() -> str:
    return "stripe" if get_settings().stripe_secret_key else "mock"


def _stripe():
    """Import and configure the SDK lazily so the app runs without it."""
    import stripe

    stripe.api_key = get_settings().stripe_secret_key
    return stripe


def _mock_ref(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


# ---------------------------------------------------------------------------
# Charging the buyer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckoutLine:
    name: str
    image_url: str
    unit_amount_cents: int
    qty: int


@dataclass(frozen=True)
class CheckoutSessionResult:
    ok: bool
    provider: str
    session_id: str
    url: str | None  # None when simulated — nothing to redirect to
    simulated: bool = False
    message: str = ""


@dataclass(frozen=True)
class SessionStatus:
    ok: bool
    paid: bool
    amount_total_cents: int
    payment_ref: str
    message: str = ""


def charge(amount_cents: int) -> PaymentResult:
    """Simulated charge, used when no Stripe key is configured.

    With Stripe configured the buyer pays through a hosted Checkout Session
    (see `create_checkout_session`) and this is never called.
    """
    if amount_cents <= 0:
        return PaymentResult(ok=False, provider="mock", ref="", message="Nothing to charge")
    return PaymentResult(ok=True, provider="mock", ref=_mock_ref("mock"), simulated=True)


def create_checkout_session(
    lines: list[CheckoutLine],
    success_url: str,
    cancel_url: str,
    customer_email: str | None = None,
) -> CheckoutSessionResult:
    """Hosted payment page. Card details never touch our servers."""
    provider = active_provider()
    if not lines:
        return CheckoutSessionResult(
            ok=False, provider=provider, session_id="", url=None, message="Cart is empty"
        )
    if provider == "mock":
        return CheckoutSessionResult(
            ok=True,
            provider="mock",
            session_id=_mock_ref("cs_mock"),
            url=None,
            simulated=True,
        )
    try:
        stripe = _stripe()
        currency = get_settings().currency
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email,
            line_items=[
                {
                    "price_data": {
                        "currency": currency,
                        "unit_amount": line.unit_amount_cents,
                        "product_data": {
                            "name": line.name,
                            # Stripe rejects non-public URLs; skip rather than fail
                            "images": [line.image_url] if line.image_url.startswith("https://") else [],
                        },
                    },
                    "quantity": line.qty,
                }
                for line in lines
            ],
        )
        return CheckoutSessionResult(
            ok=True, provider="stripe", session_id=session.id, url=session.url
        )
    except Exception as e:  # noqa: BLE001
        return CheckoutSessionResult(
            ok=False, provider="stripe", session_id="", url=None, message=str(e)
        )


def retrieve_checkout_session(session_id: str) -> SessionStatus:
    """Did this session actually get paid? Stripe is the authority, not the
    browser that came back to our return URL."""
    if active_provider() == "mock":
        return SessionStatus(
            ok=True, paid=True, amount_total_cents=0, payment_ref=session_id
        )
    try:
        session = _stripe().checkout.Session.retrieve(session_id)
        return SessionStatus(
            ok=True,
            paid=session.payment_status == "paid",
            amount_total_cents=int(session.amount_total or 0),
            payment_ref=str(session.payment_intent or session.id),
        )
    except Exception as e:  # noqa: BLE001
        return SessionStatus(
            ok=False, paid=False, amount_total_cents=0, payment_ref="", message=str(e)
        )


def verify_webhook(payload: bytes, signature: str) -> dict | None:
    """Validate a Stripe webhook signature. None means reject the request."""
    secret = get_settings().stripe_webhook_secret
    if not secret:
        return None
    try:
        return _stripe().Webhook.construct_event(payload, signature, secret)
    except Exception:  # noqa: BLE001 — bad signature or malformed payload
        return None


# ---------------------------------------------------------------------------
# Seller onboarding (Stripe Connect Express)
# ---------------------------------------------------------------------------

def create_connect_account(email: str, brand_name: str | None = None) -> AccountResult:
    """Create the seller's connected account (no identity details yet)."""
    provider = active_provider()
    if provider == "mock":
        return AccountResult(
            ok=True, provider="mock", account_id=_mock_ref("acct_mock"), simulated=True
        )
    try:
        stripe = _stripe()
        account = stripe.Account.create(
            type="express",
            email=email,
            business_profile={"name": brand_name} if brand_name else None,
            capabilities={"transfers": {"requested": True}},
        )
        return AccountResult(ok=True, provider="stripe", account_id=account.id)
    except Exception as e:  # noqa: BLE001 — surfaced to the seller as a 502
        return AccountResult(ok=False, provider="stripe", account_id="", message=str(e))


def onboarding_link(account_id: str, return_url: str, refresh_url: str) -> OnboardingResult:
    """Single-use Stripe-hosted onboarding URL (identity, bank details)."""
    provider = active_provider()
    if provider == "mock":
        # Nothing to visit; the caller marks the seller payout-ready itself.
        return OnboardingResult(ok=True, provider="mock", url=None, simulated=True)
    try:
        stripe = _stripe()
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
        return OnboardingResult(ok=True, provider="stripe", url=link.url)
    except Exception as e:  # noqa: BLE001
        return OnboardingResult(ok=False, provider="stripe", url=None, message=str(e))


def account_payouts_enabled(account_id: str) -> bool:
    """Has this seller finished verification and can receive transfers?"""
    if active_provider() == "mock":
        return True
    try:
        return bool(_stripe().Account.retrieve(account_id).payouts_enabled)
    except Exception:  # noqa: BLE001 — treat an unreachable Stripe as "not yet"
        return False


# ---------------------------------------------------------------------------
# Paying sellers
# ---------------------------------------------------------------------------

def transfer(
    amount_cents: int, destination_account_id: str, order_id: str
) -> TransferResult:
    """Move the seller's net share from the platform balance to their account."""
    provider = active_provider()
    if amount_cents <= 0:
        return TransferResult(
            ok=False, provider=provider, ref="", message="Nothing to transfer"
        )
    if provider == "mock":
        return TransferResult(
            ok=True, provider="mock", ref=_mock_ref("tr_mock"), simulated=True
        )
    try:
        stripe = _stripe()
        tr = stripe.Transfer.create(
            amount=amount_cents,
            currency=get_settings().currency,
            destination=destination_account_id,
            transfer_group=f"order_{order_id}",
            # Makes retries safe: Stripe collapses duplicates by this key
            idempotency_key=f"payout_{order_id}_{destination_account_id}",
        )
        return TransferResult(ok=True, provider="stripe", ref=tr.id)
    except Exception as e:  # noqa: BLE001
        return TransferResult(ok=False, provider="stripe", ref="", message=str(e))
