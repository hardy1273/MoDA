"""Shared test fixtures.

Settings are read from .env, which means the suite would otherwise behave
differently depending on whether the developer happens to have a Stripe key
configured. Tests must be hermetic, so payments default to the simulated
provider here regardless of local config; tests that want the Stripe path
opt in explicitly via the `stripe_configured` fixture.
"""

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def simulated_payments(monkeypatch):
    """Force the mock payment provider for every test."""
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "")
    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "")


@pytest.fixture
def stripe_configured(monkeypatch):
    """Pretend a Stripe key is present (no network calls are made)."""
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "sk_test_fixture")
