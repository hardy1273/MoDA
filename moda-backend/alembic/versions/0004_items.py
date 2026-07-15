"""Items catalog + shop-the-look links.

items: individual purchasable pieces with their own CLIP embedding and
placeholder prices. outfit_items: visually-similar items per outfit,
populated by scripts/link_items.py.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-14

"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

DIM = 512


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("style_tags", ARRAY(sa.String()), nullable=False),
        sa.Column("color_tags", ARRAY(sa.String()), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_items_category", "items", ["category"])
    op.create_index(
        "ix_items_embedding_cosine",
        "items",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "outfit_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("outfit_id", UUID(as_uuid=True), sa.ForeignKey("outfits.id"), nullable=False),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.UniqueConstraint("outfit_id", "item_id", name="uq_outfit_item"),
    )
    op.create_index("ix_outfit_items_outfit_id", "outfit_items", ["outfit_id"])
    op.create_index("ix_outfit_items_item_id", "outfit_items", ["item_id"])


def downgrade() -> None:
    op.drop_table("outfit_items")
    op.drop_table("items")
