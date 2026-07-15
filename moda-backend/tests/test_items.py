import uuid

from scripts.fetch_items import item_name, placeholder_price_cents
from scripts.link_items import pick_shop_the_look


class TestPlaceholderPrice:
    def test_deterministic(self):
        assert placeholder_price_cents("abc123", 40, 120) == placeholder_price_cents(
            "abc123", 40, 120
        )

    def test_within_category_range(self):
        for pid in ("a", "b", "c", "photo-xyz", "q1w2e3"):
            cents = placeholder_price_cents(pid, 60, 200)
            assert 60_00 <= cents <= 200_99

    def test_psychological_price_endings(self):
        assert placeholder_price_cents("x", 10, 20) % 100 in (49, 99)

    def test_different_photos_spread_prices(self):
        prices = {placeholder_price_cents(f"photo-{i}", 40, 300) for i in range(50)}
        assert len(prices) > 25


class TestItemName:
    def test_color_plus_category(self):
        photo = {"color": "#0d0d0d"}
        assert item_name(photo, "hoodie") == "Black hoodie"

    def test_no_color_falls_back_to_category(self):
        assert item_name({}, "sneakers") == "Sneakers"


class TestPickShopTheLook:
    def _c(self, category, score):
        return (uuid.uuid4(), category, score)

    def test_one_item_per_category(self):
        cands = [self._c("hoodie", 0.9), self._c("hoodie", 0.85), self._c("jeans", 0.8)]
        picks = pick_shop_the_look(cands, max_items=5, min_score=0.0)
        assert len(picks) == 2
        assert picks[0][1] == 0.9  # best hoodie kept, duplicate category dropped

    def test_respects_max_items(self):
        cands = [self._c(f"cat{i}", 0.9 - i * 0.01) for i in range(10)]
        assert len(pick_shop_the_look(cands, max_items=4, min_score=0.0)) == 4

    def test_filters_below_min_score(self):
        cands = [self._c("hoodie", 0.9), self._c("jeans", 0.3)]
        picks = pick_shop_the_look(cands, max_items=5, min_score=0.45)
        assert len(picks) == 1

    def test_empty_candidates(self):
        assert pick_shop_the_look([], max_items=5, min_score=0.4) == []
