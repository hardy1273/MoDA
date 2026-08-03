"""Splitting an order into per-seller payouts.

A single cart can hold pieces from several sellers plus platform-owned
(seeded) catalog items, so one customer charge fans out into N transfers.
This module is pure arithmetic over plain data — no database, no Stripe —
so the money math is unit-testable in isolation.

Money is always integer cents. The invariant that matters:

    fee_cents + net_cents == gross_cents        (exactly, per seller)
    sum(gross_cents) + platform_only == order total

Rounding never invents or destroys a cent: the fee is rounded, and the
seller's net is whatever remains.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class SellerSplit:
    seller_id: uuid.UUID
    gross_cents: int  # what buyers paid for this seller's lines
    fee_cents: int  # platform commission
    net_cents: int  # transferred to the seller

    @property
    def gross(self) -> float:
        return self.gross_cents / 100

    @property
    def fee(self) -> float:
        return self.fee_cents / 100

    @property
    def net(self) -> float:
        return self.net_cents / 100


def platform_fee_cents(gross_cents: int, fee_bps: int) -> int:
    """Commission on `gross_cents`, in basis points (1000 bps = 10%).

    Rounds half-up to the nearest cent, and never exceeds the gross or
    drops below zero — a misconfigured rate can't produce a negative
    payout or charge a seller more than they sold.
    """
    if gross_cents <= 0 or fee_bps <= 0:
        return 0
    fee = (gross_cents * fee_bps + 5_000) // 10_000
    return min(int(fee), gross_cents)


def split_order(
    lines: list[tuple[uuid.UUID | None, int, int]], fee_bps: int
) -> list[SellerSplit]:
    """Group order lines by seller and compute each seller's cut.

    `lines` are (seller_id, price_cents, qty) triples. Lines with a NULL
    seller are platform-owned seeded catalog stock — they produce no
    payout, so the platform simply keeps that revenue.

    Fees are computed on each seller's *combined* gross rather than
    per line, so a seller with three cheap items isn't rounded against
    three separate times.
    """
    gross_by_seller: dict[uuid.UUID, int] = {}
    for seller_id, price_cents, qty in lines:
        if seller_id is None:
            continue
        gross_by_seller[seller_id] = gross_by_seller.get(seller_id, 0) + price_cents * qty

    splits: list[SellerSplit] = []
    for seller_id, gross in sorted(gross_by_seller.items(), key=lambda kv: str(kv[0])):
        fee = platform_fee_cents(gross, fee_bps)
        splits.append(
            SellerSplit(
                seller_id=seller_id,
                gross_cents=gross,
                fee_cents=fee,
                net_cents=gross - fee,
            )
        )
    return splits


def platform_revenue_cents(order_total_cents: int, splits: list[SellerSplit]) -> int:
    """What the platform keeps: commission plus all platform-owned stock."""
    seller_net = sum(s.net_cents for s in splits)
    return order_total_cents - seller_net
