import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base

DIM = get_settings().embedding_dim


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Listing lifecycle. Only APPROVED reaches shoppers; REMOVED is a soft delete
# (hard deletes would break order-history and cart foreign keys).
ITEM_PENDING = "pending"
ITEM_APPROVED = "approved"
ITEM_REJECTED = "rejected"
ITEM_REMOVED = "removed"
ITEM_STATUSES = (ITEM_PENDING, ITEM_APPROVED, ITEM_REJECTED, ITEM_REMOVED)


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

    # Seller role: any shopper can upgrade by claiming a brand name
    is_seller: Mapped[bool] = mapped_column(Boolean, default=False)
    brand_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Stripe Connect (Express). Set once onboarding starts; payouts_enabled
    # mirrors Stripe's own flag and is only true after they finish identity
    # verification — until then earnings accrue as pending payouts.
    stripe_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payouts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Moderators who review the listing queue (granted via scripts/grant_admin.py)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

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


class Item(Base):
    """An individual purchasable piece (hoodie, sneakers, …).

    Seeded catalog rows have no seller and carry placeholder prices;
    seller-created listings set their own and enter the approval queue.
    Only `approved` items are visible to shoppers.
    """

    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), index=True)
    image_url: Mapped[str] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    style_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    color_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    price_cents: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # NULL for the seeded catalog; set for seller listings
    seller_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    # pending | approved | rejected | removed  (see ITEM_STATUSES)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # Moderator note shown to the seller when a listing is rejected
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    seller: Mapped["User | None"] = relationship()

    @property
    def price(self) -> float:
        return self.price_cents / 100

    @property
    def brand_name(self) -> str | None:
        return self.seller.brand_name if self.seller else None

    __table_args__ = (
        Index(
            "ix_items_embedding_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class OutfitItem(Base):
    """Shop-the-look link: visually similar items for an outfit."""

    __tablename__ = "outfit_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    outfit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outfits.id"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    # cosine similarity between outfit and item embeddings at link time
    score: Mapped[float] = mapped_column(Float)

    item: Mapped["Item"] = relationship()

    __table_args__ = (
        UniqueConstraint("outfit_id", "item_id", name="uq_outfit_item"),
    )


class CartItem(Base):
    """Server-side cart line for a logged-in user."""

    __tablename__ = "cart_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    size: Mapped[str] = mapped_column(String(16))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    item: Mapped["Item"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "item_id", "size", name="uq_cart_line"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="paid")
    total_cents: Mapped[int] = mapped_column(Integer)
    payment_provider: Mapped[str] = mapped_column(String(24))
    payment_ref: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", order_by="OrderItem.name"
    )

    @property
    def total(self) -> float:
        return self.total_cents / 100


class OrderItem(Base):
    """Order line with name/price snapshotted at purchase time."""

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    name: Mapped[str] = mapped_column(String(120))
    image_url: Mapped[str] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer)
    size: Mapped[str] = mapped_column(String(16))
    qty: Mapped[int] = mapped_column(Integer)
    # Snapshot of who sold this line; NULL = platform-owned seeded stock.
    # Kept on the order so payouts survive a seller deleting the listing.
    seller_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    order: Mapped["Order"] = relationship(back_populates="items")

    @property
    def price(self) -> float:
        return self.price_cents / 100


# Payout lifecycle
PAYOUT_PENDING = "pending"  # owed, but the seller can't receive it yet
PAYOUT_PAID = "paid"
PAYOUT_FAILED = "failed"
PAYOUT_STATUSES = (PAYOUT_PENDING, PAYOUT_PAID, PAYOUT_FAILED)


class Payout(Base):
    """One seller's share of one order.

    Created at checkout for every seller in the cart. Transfers to sellers
    who haven't finished Stripe onboarding stay `pending` until they do,
    which mirrors how Stripe itself holds funds.
    """

    __tablename__ = "payouts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), index=True
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )

    gross_cents: Mapped[int] = mapped_column(Integer)
    fee_cents: Mapped[int] = mapped_column(Integer)
    net_cents: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(16), default=PAYOUT_PENDING, index=True)
    provider: Mapped[str] = mapped_column(String(24))
    transfer_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["Order"] = relationship()

    @property
    def gross(self) -> float:
        return self.gross_cents / 100

    @property
    def fee(self) -> float:
        return self.fee_cents / 100

    @property
    def net(self) -> float:
        return self.net_cents / 100

    __table_args__ = (
        UniqueConstraint("order_id", "seller_id", name="uq_payout_order_seller"),
    )


class Impression(Base):
    """How often an outfit was shown to a user without interaction.

    Fed back into ranking as a small fatigue penalty so the feed doesn't
    keep resurfacing pieces the user has scrolled past repeatedly.
    """

    __tablename__ = "impressions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    outfit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("outfits.id"))
    count: Mapped[int] = mapped_column(Integer, default=1)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "outfit_id", name="uq_impression"),
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
