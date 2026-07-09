"""Replace the ivfflat outfit-embedding index with HNSW.

ivfflat with lists=100 has a recall cliff on small datasets: with
pgvector's default probes=1, a query scans only the single nearest
centroid's list (~rows/100 vectors). At MVP catalog size (~800 rows)
that returned near-random candidates and every user got the same feed.
HNSW recall is independent of row count and needs no post-ingest
rebuild.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-09

"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_outfits_embedding_cosine", table_name="outfits")
    op.create_index(
        "ix_outfits_embedding_cosine",
        "outfits",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_outfits_embedding_cosine", table_name="outfits")
    op.create_index(
        "ix_outfits_embedding_cosine",
        "outfits",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
