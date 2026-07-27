"""Seller role + listing approval queue.

Adds is_seller/brand_name/is_admin to users and seller_id/status/review_note
to items. The seeded catalog predates moderation, so existing rows are
grandfathered as approved.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-17

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_seller", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("brand_name", sa.String(80), nullable=True))
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("items", sa.Column("seller_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    # server_default approves the existing seeded catalog in place; new rows
    # get "pending" from the model default
    op.add_column("items", sa.Column("status", sa.String(16), nullable=False, server_default="approved"))
    op.add_column("items", sa.Column("review_note", sa.Text(), nullable=True))
    op.create_index("ix_items_seller_id", "items", ["seller_id"])
    op.create_index("ix_items_status", "items", ["status"])

    # Drop the server_default so the application default ("pending") governs
    op.alter_column("items", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_items_status", table_name="items")
    op.drop_index("ix_items_seller_id", table_name="items")
    op.drop_column("items", "review_note")
    op.drop_column("items", "status")
    op.drop_column("items", "seller_id")
    op.drop_column("users", "is_admin")
    op.drop_column("users", "brand_name")
    op.drop_column("users", "is_seller")
