import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth / Users ----------

class SignupIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    username: str
    profile_text: str | None = None
    is_seller: bool = False
    brand_name: str | None = None
    is_admin: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Quiz ----------

class QuizSubmission(BaseModel):
    aesthetics: list[str] = Field(default_factory=list, examples=[["minimal", "streetwear"]])
    colors: list[str] = Field(default_factory=list, examples=[["black", "neutral tones"]])
    fits: list[str] = Field(default_factory=list, examples=[["oversized", "tailored"]])
    brands: list[str] = Field(default_factory=list)
    occasions: list[str] = Field(default_factory=list, examples=[["everyday", "nightlife"]])
    inspirations: list[str] = Field(default_factory=list)
    liked_outfit_ids: list[uuid.UUID] = Field(default_factory=list)
    disliked_outfit_ids: list[uuid.UUID] = Field(default_factory=list)


class QuizResult(BaseModel):
    user_id: uuid.UUID
    profile_text: str


# ---------- Outfits / Feed ----------

class OutfitOut(BaseModel):
    id: uuid.UUID
    image_url: str
    caption: str | None
    style_tags: list[str]
    color_tags: list[str]
    occasion_tags: list[str]

    model_config = {"from_attributes": True}


class RecommendationOut(BaseModel):
    outfit: OutfitOut
    score: float
    explanation: str


class FeedOut(BaseModel):
    user_id: uuid.UUID
    items: list[RecommendationOut]


# ---------- Items ----------

class ItemOut(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    image_url: str
    caption: str | None
    style_tags: list[str]
    color_tags: list[str]
    price: float  # dollars
    brand_name: str | None = None  # None for the seeded catalog

    model_config = {"from_attributes": True}


# ---------- Seller ----------

class SellerUpgradeIn(BaseModel):
    brand_name: str = Field(min_length=2, max_length=80)


class SellerOut(BaseModel):
    id: uuid.UUID
    username: str
    is_seller: bool
    brand_name: str | None
    is_admin: bool

    model_config = {"from_attributes": True}


class ListingIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=40)
    image_url: str = Field(min_length=8)
    price: float = Field(gt=0, le=100_000)
    caption: str | None = Field(default=None, max_length=500)
    style_tags: list[str] = Field(default_factory=list, max_length=10)
    color_tags: list[str] = Field(default_factory=list, max_length=10)


class ListingUpdate(BaseModel):
    """All fields optional; only what's provided is changed."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    category: str | None = Field(default=None, min_length=2, max_length=40)
    image_url: str | None = Field(default=None, min_length=8)
    price: float | None = Field(default=None, gt=0, le=100_000)
    caption: str | None = Field(default=None, max_length=500)
    style_tags: list[str] | None = Field(default=None, max_length=10)
    color_tags: list[str] | None = Field(default=None, max_length=10)


class ListingOut(BaseModel):
    """A listing as its own seller (or a moderator) sees it."""

    id: uuid.UUID
    name: str
    category: str
    image_url: str
    caption: str | None
    style_tags: list[str]
    color_tags: list[str]
    price: float
    status: str
    review_note: str | None
    brand_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


# ---------- Payouts ----------

class PayoutStatusOut(BaseModel):
    """Whether this seller can currently be paid."""

    onboarding_started: bool
    payouts_enabled: bool
    provider: str
    simulated: bool
    pending_cents: int
    paid_cents: int

    @property
    def pending(self) -> float:
        return self.pending_cents / 100


class OnboardingOut(BaseModel):
    ok: bool
    # None when simulated — there's no hosted page to visit
    url: str | None = None
    simulated: bool = False
    payouts_enabled: bool = False


class PayoutOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    gross: float
    fee: float
    net: float
    status: str
    provider: str
    transfer_ref: str | None
    failure_reason: str | None
    created_at: datetime
    paid_at: datetime | None

    model_config = {"from_attributes": True}


class EarningsOut(BaseModel):
    brand_name: str | None
    payouts_enabled: bool
    lifetime_gross: float
    lifetime_fees: float
    lifetime_net: float
    pending_net: float
    payouts: list[PayoutOut]


# ---------- Cart / Orders ----------

class CartLineIn(BaseModel):
    item_id: uuid.UUID
    size: str = Field(min_length=1, max_length=16)
    qty: int = Field(default=1, ge=1, le=20)


class CartLineQty(BaseModel):
    qty: int = Field(ge=0, le=20)  # 0 removes the line


class CartLineOut(BaseModel):
    id: uuid.UUID
    item: ItemOut
    size: str
    qty: int

    model_config = {"from_attributes": True}


class CartOut(BaseModel):
    items: list[CartLineOut]
    total: float  # dollars


class OrderItemOut(BaseModel):
    name: str
    image_url: str
    price: float
    size: str
    qty: int

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: uuid.UUID
    status: str
    total: float
    payment_provider: str
    payment_ref: str
    created_at: datetime
    items: list[OrderItemOut]

    model_config = {"from_attributes": True}


# ---------- Impressions ----------

class ImpressionsIn(BaseModel):
    outfit_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


# ---------- Feedback ----------

class FeedbackIn(BaseModel):
    outfit_id: uuid.UUID
    interaction_type: str = Field(pattern="^(like|dislike|save|skip)$")


class FeedbackOut(BaseModel):
    ok: bool
    interaction_type: str
    user_embedding_updated: bool
