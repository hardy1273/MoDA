"""Payout splitting and fee arithmetic.

Money bugs are silent and expensive, so these lean on invariants rather
than hand-computed examples wherever possible.
"""

import uuid

import pytest

from app.payments import (
    account_payouts_enabled,
    active_provider,
    charge,
    create_connect_account,
    onboarding_link,
    transfer,
)
from app.payouts import (
    SellerSplit,
    platform_fee_cents,
    platform_revenue_cents,
    split_order,
)

TEN_PCT = 1000  # basis points


class TestPlatformFee:
    def test_ten_percent_of_round_amount(self):
        assert platform_fee_cents(10_000, TEN_PCT) == 1_000

    def test_rounds_half_up(self):
        # 5 cents at 10% = 0.5 cents -> 1
        assert platform_fee_cents(5, TEN_PCT) == 1
        # 4 cents at 10% = 0.4 cents -> 0
        assert platform_fee_cents(4, TEN_PCT) == 0

    def test_zero_rate_means_no_commission(self):
        assert platform_fee_cents(9_999, 0) == 0

    def test_zero_and_negative_gross(self):
        assert platform_fee_cents(0, TEN_PCT) == 0
        assert platform_fee_cents(-500, TEN_PCT) == 0

    def test_fee_never_exceeds_gross(self):
        # A misconfigured 200% rate must not produce a negative payout
        assert platform_fee_cents(1_000, 20_000) == 1_000

    @pytest.mark.parametrize("gross", [1, 7, 99, 100, 4_999, 14_800, 1_234_567])
    def test_fee_within_bounds(self, gross):
        fee = platform_fee_cents(gross, TEN_PCT)
        assert 0 <= fee <= gross


class TestSplitOrder:
    def test_single_seller(self):
        s = uuid.uuid4()
        splits = split_order([(s, 10_000, 1)], TEN_PCT)
        assert len(splits) == 1
        assert splits[0] == SellerSplit(s, gross_cents=10_000, fee_cents=1_000, net_cents=9_000)

    def test_quantity_multiplies_gross(self):
        s = uuid.uuid4()
        (split,) = split_order([(s, 2_500, 3)], TEN_PCT)
        assert split.gross_cents == 7_500

    def test_multiple_sellers_split_separately(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        splits = split_order([(a, 10_000, 1), (b, 5_000, 1)], TEN_PCT)
        assert len(splits) == 2
        assert {s.seller_id for s in splits} == {a, b}
        assert {s.net_cents for s in splits} == {9_000, 4_500}

    def test_lines_from_same_seller_combine_before_fee(self):
        """Fee on the combined gross, not per line — avoids repeated rounding."""
        s = uuid.uuid4()
        (split,) = split_order([(s, 5, 1), (s, 5, 1)], TEN_PCT)
        assert split.gross_cents == 10
        assert split.fee_cents == 1  # not 2, which per-line rounding would give

    def test_platform_owned_items_produce_no_payout(self):
        splits = split_order([(None, 12_000, 2)], TEN_PCT)
        assert splits == []

    def test_mixed_cart_only_pays_sellers(self):
        s = uuid.uuid4()
        splits = split_order([(None, 9_900, 1), (s, 10_000, 1)], TEN_PCT)
        assert len(splits) == 1
        assert splits[0].seller_id == s

    def test_empty_order(self):
        assert split_order([], TEN_PCT) == []

    def test_ordering_is_deterministic(self):
        a, b, c = sorted([uuid.uuid4() for _ in range(3)], key=str)
        lines = [(c, 100, 1), (a, 100, 1), (b, 100, 1)]
        assert [s.seller_id for s in split_order(lines, TEN_PCT)] == [a, b, c]

    @pytest.mark.parametrize("price,qty", [(1, 1), (7, 3), (14_800, 2), (99, 7)])
    def test_fee_plus_net_always_equals_gross(self, price, qty):
        """The invariant: splitting never creates or loses a cent."""
        s = uuid.uuid4()
        (split,) = split_order([(s, price, qty)], TEN_PCT)
        assert split.fee_cents + split.net_cents == split.gross_cents
        assert split.gross_cents == price * qty

    def test_dollar_properties(self):
        s = uuid.uuid4()
        (split,) = split_order([(s, 14_800, 1)], TEN_PCT)
        assert split.gross == 148.0
        assert split.fee == 14.8
        assert split.net == 133.2


class TestPlatformRevenue:
    def test_commission_only_when_all_items_have_sellers(self):
        s = uuid.uuid4()
        splits = split_order([(s, 10_000, 1)], TEN_PCT)
        assert platform_revenue_cents(10_000, splits) == 1_000

    def test_includes_full_price_of_platform_owned_stock(self):
        s = uuid.uuid4()
        splits = split_order([(s, 10_000, 1), (None, 5_000, 1)], TEN_PCT)
        # 1,000 commission + 5,000 of own stock
        assert platform_revenue_cents(15_000, splits) == 6_000

    def test_no_sellers_means_platform_keeps_everything(self):
        assert platform_revenue_cents(7_777, []) == 7_777


class TestMockProvider:
    """With no STRIPE_SECRET_KEY the simulated provider must still work."""

    def test_provider_is_mock_without_key(self):
        assert active_provider() == "mock"

    def test_charge_succeeds_and_is_flagged_simulated(self):
        r = charge(12_345)
        assert r.ok and r.simulated and r.ref.startswith("mock_")

    def test_charge_rejects_zero(self):
        assert not charge(0).ok

    def test_connect_account_created(self):
        r = create_connect_account("seller@example.com", "Atelier Nine")
        assert r.ok and r.simulated and r.account_id.startswith("acct_mock")

    def test_onboarding_has_no_url_when_simulated(self):
        r = onboarding_link("acct_mock_x", "https://a/return", "https://a/refresh")
        assert r.ok and r.simulated and r.url is None

    def test_account_reports_payouts_enabled(self):
        assert account_payouts_enabled("acct_mock_x") is True

    def test_transfer_succeeds(self):
        r = transfer(9_000, "acct_mock_x", str(uuid.uuid4()))
        assert r.ok and r.simulated and r.ref.startswith("tr_mock")

    def test_transfer_rejects_non_positive(self):
        assert not transfer(0, "acct_mock_x", "order").ok
        assert not transfer(-100, "acct_mock_x", "order").ok
