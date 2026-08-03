"""Seller payouts via Stripe Connect.

Adds Connect fields to users, a seller snapshot on order lines, and the
payouts table (one row per order+seller).

Existing order_items get seller_id = NULL, which is correct: everything
sold before this migration was platform-owned seeded stock.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-18

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_account_id", sa.String(64), nullable=True))
    op.add_column(
        "users",
        sa.Column("payouts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column(
        "order_items",
        sa.Column("seller_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "payouts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("seller_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("gross_cents", sa.Integer(), nullable=False),
        sa.Column("fee_cents", sa.Integer(), nullable=False),
        sa.Column("net_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("transfer_ref", sa.String(64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("order_id", "seller_id", name="uq_payout_order_seller"),
    )
    op.create_index("ix_payouts_order_id", "payouts", ["order_id"])
    op.create_index("ix_payouts_seller_id", "payouts", ["seller_id"])
    op.create_index("ix_payouts_status", "payouts", ["status"])


def downgrade() -> None:
    op.drop_table("payouts")
    op.drop_column("order_items", "seller_id")
    op.drop_column("users", "payouts_enabled")
    op.drop_column("users", "stripe_account_id")
