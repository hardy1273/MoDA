"""Impression tracking (feed fatigue signal).

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-16

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "impressions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("outfit_id", UUID(as_uuid=True), sa.ForeignKey("outfits.id"), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "outfit_id", name="uq_impression"),
    )
    op.create_index("ix_impressions_user_id", "impressions", ["user_id"])


def downgrade() -> None:
    op.drop_table("impressions")
