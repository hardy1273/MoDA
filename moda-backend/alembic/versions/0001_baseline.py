"""Baseline schema: users, outfits, interactions (pgvector).

Matches the schema previously created by Base.metadata.create_all().
The vector dimension is frozen at 512 (OpenCLIP ViT-B/32); changing
EMBEDDING_DIM requires a new migration plus re-ingesting outfits.

Revision ID: 0001
Revises:
Create Date: 2026-07-02

"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DIM = 512


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("profile_text", sa.Text(), nullable=True),
        sa.Column("quiz_embedding", Vector(DIM), nullable=True),
        sa.Column("embedding", Vector(DIM), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "outfits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("style_tags", ARRAY(sa.String()), nullable=False),
        sa.Column("color_tags", ARRAY(sa.String()), nullable=False),
        sa.Column("occasion_tags", ARRAY(sa.String()), nullable=False),
        sa.Column("embedding", Vector(DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_outfits_embedding_cosine",
        "outfits",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "interactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("outfit_id", UUID(as_uuid=True), sa.ForeignKey("outfits.id"), nullable=False),
        sa.Column("interaction_type", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "outfit_id", "interaction_type", name="uq_interaction"),
    )
    op.create_index("ix_interactions_user_id", "interactions", ["user_id"])
    op.create_index("ix_interactions_outfit_id", "interactions", ["outfit_id"])


def downgrade() -> None:
    op.drop_table("interactions")
    op.drop_table("outfits")
    op.drop_table("users")
