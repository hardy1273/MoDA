"""Add users.password_hash for JWT auth.

Nullable: users created before auth have no password and cannot log in
until one is set.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-02

"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
