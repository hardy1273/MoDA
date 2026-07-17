"""Payment provider abstraction.

Only the mock provider exists today: it always succeeds and returns a
reference. The interface is shaped so a Stripe provider (Checkout Session /
PaymentIntent, and later Connect for seller payouts) can drop in behind
`charge()` without touching the checkout endpoint.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentResult:
    ok: bool
    provider: str
    ref: str
    message: str = ""


def charge(amount_cents: int, provider: str = "mock") -> PaymentResult:
    if amount_cents <= 0:
        return PaymentResult(ok=False, provider=provider, ref="", message="Nothing to charge")
    if provider == "mock":
        return PaymentResult(ok=True, provider="mock", ref=f"mock_{uuid.uuid4().hex[:16]}")
    return PaymentResult(
        ok=False, provider=provider, ref="", message=f"Unknown payment provider: {provider}"
    )
