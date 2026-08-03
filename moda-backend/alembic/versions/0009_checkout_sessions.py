"""Stripe Checkout session tracking.

Two columns, both about not losing or duplicating an order when payment
happens on Stripe's servers rather than ours:

  orders.payment_session_id      unique — the idempotency key, so a
                                 refreshed return URL and the webhook
                                 can't both create an order
  cart_items.checkout_session_id locks lines to an in-flight session, so
                                 editing the cart mid-payment can't change
                                 what was actually bought

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-02

"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("payment_session_id", sa.String(128), nullable=True))
    op.create_unique_constraint("uq_orders_payment_session", "orders", ["payment_session_id"])

    op.add_column(
        "cart_items", sa.Column("checkout_session_id", sa.String(128), nullable=True)
    )
    op.create_index(
        "ix_cart_items_checkout_session", "cart_items", ["checkout_session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_cart_items_checkout_session", table_name="cart_items")
    op.drop_column("cart_items", "checkout_session_id")
    op.drop_constraint("uq_orders_payment_session", "orders", type_="unique")
    op.drop_column("orders", "payment_session_id")
