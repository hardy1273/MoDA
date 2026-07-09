import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base

DIM = get_settings().embedding_dim


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Nullable so users created before auth landed keep working (they just
    # can't log in until a password is set)
    password_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    profile_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Frozen embedding from the onboarding quiz (the "anchor" of taste)
    quiz_embedding: Mapped[list[float] | None] = mapped_column(Vector(DIM), nullable=True)
    # Live, blended embedding used for retrieval (updates with feedback)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(DIM), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interactions: Mapped[list["Interaction"]] = relationship(back_populates="user")


class Outfit(Base):
    __tablename__ = "outfits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    image_url: Mapped[str] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    style_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    color_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    occasion_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    embedding: Mapped[list[float]] = mapped_column(Vector(DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        # HNSW index for approximate nearest-neighbor search (cosine).
        # Chosen over ivfflat: recall doesn't depend on row count vs a fixed
        # `lists` (ivfflat with lists=100 on a few hundred rows returned ~1%
        # of vectors per probe and made every feed nearly identical).
        Index(
            "ix_outfits_embedding_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    outfit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outfits.id"), index=True
    )
    # like | dislike | save | skip
    interaction_type: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="interactions")
    outfit: Mapped["Outfit"] = relationship()

    __table_args__ = (
        # One row per (user, outfit, type); re-submitting the same action is idempotent
        UniqueConstraint("user_id", "outfit_id", "interaction_type", name="uq_interaction"),
    )
