"""Seller portal: listing validation, image-URL guards, status lifecycle."""

import pytest
from pydantic import ValidationError

from app import models
from app.catalog import validate_listing_image_url
from app.schemas import ListingIn, ListingUpdate, SellerUpgradeIn


class TestValidateListingImageUrl:
    def test_accepts_https(self):
        assert validate_listing_image_url("https://example.com/a.jpg") == "https://example.com/a.jpg"

    def test_strips_whitespace(self):
        assert validate_listing_image_url("  https://example.com/a.jpg  ").startswith("https://")

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/a.jpg",
            "/local/path.jpg",
            "data:image/png;base64,AAAA",
            "javascript:alert(1)",
        ],
    )
    def test_rejects_non_http_schemes(self, url):
        with pytest.raises(ValueError):
            validate_listing_image_url(url)


class TestListingIn:
    def _valid(self, **over):
        base = {
            "name": "Black hoodie",
            "category": "hoodie",
            "image_url": "https://example.com/hoodie.jpg",
            "price": 89.99,
        }
        base.update(over)
        return base

    def test_valid_listing(self):
        listing = ListingIn(**self._valid())
        assert listing.price == 89.99
        assert listing.style_tags == []

    @pytest.mark.parametrize("price", [0, -5, 100_001])
    def test_price_bounds(self, price):
        with pytest.raises(ValidationError):
            ListingIn(**self._valid(price=price))

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            ListingIn(**self._valid(name="x"))

    def test_tag_count_capped(self):
        with pytest.raises(ValidationError):
            ListingIn(**self._valid(style_tags=[f"t{i}" for i in range(11)]))


class TestListingUpdate:
    def test_all_fields_optional(self):
        u = ListingUpdate()
        assert u.name is None and u.price is None

    def test_partial_update(self):
        assert ListingUpdate(price=42.0).price == 42.0

    def test_still_validates_provided_fields(self):
        with pytest.raises(ValidationError):
            ListingUpdate(price=-1)


class TestSellerUpgradeIn:
    def test_valid_brand(self):
        assert SellerUpgradeIn(brand_name="Atelier Nine").brand_name == "Atelier Nine"

    def test_brand_too_short(self):
        with pytest.raises(ValidationError):
            SellerUpgradeIn(brand_name="a")


class TestStatusConstants:
    def test_new_items_default_to_pending(self):
        assert models.Item.__table__.c.status.default.arg == models.ITEM_PENDING

    def test_all_statuses_registered(self):
        assert set(models.ITEM_STATUSES) == {"pending", "approved", "rejected", "removed"}


class TestPriceConversion:
    """Dollars in the API, cents in the DB."""

    @pytest.mark.parametrize(
        "dollars,cents", [(89.99, 8999), (0.99, 99), (1200.5, 120050), (19.995, 2000)]
    )
    def test_round_to_cents(self, dollars, cents):
        assert round(dollars * 100) == cents
