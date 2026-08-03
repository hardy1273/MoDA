import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.main import cart_total_cents
from app.payments import charge
from app.schemas import CartLineIn, CartLineQty


def line(price_cents: int, qty: int):
    return SimpleNamespace(item=SimpleNamespace(price_cents=price_cents), qty=qty)


class TestCartTotal:
    def test_sums_price_times_qty(self):
        assert cart_total_cents([line(4999, 2), line(12049, 1)]) == 4999 * 2 + 12049

    def test_empty_cart_is_zero(self):
        assert cart_total_cents([]) == 0


class TestMockPayments:
    def test_charge_succeeds_with_reference(self):
        r = charge(12345)
        assert r.ok and r.provider == "mock" and r.ref.startswith("mock_")

    def test_references_are_unique(self):
        assert charge(100).ref != charge(100).ref

    def test_zero_amount_rejected(self):
        r = charge(0)
        assert not r.ok

    def test_charging_is_flagged_simulated(self):
        # Card collection isn't built; the flag must say so even once
        # Stripe is configured for payouts.
        assert charge(100).simulated is True


class TestCartSchemas:
    def test_qty_defaults_to_one(self):
        assert CartLineIn(item_id=uuid.uuid4(), size="M").qty == 1

    @pytest.mark.parametrize("qty", [0, -1, 21])
    def test_add_qty_bounds(self, qty):
        with pytest.raises(ValidationError):
            CartLineIn(item_id=uuid.uuid4(), size="M", qty=qty)

    def test_qty_zero_allowed_for_update(self):
        assert CartLineQty(qty=0).qty == 0  # 0 = remove the line
