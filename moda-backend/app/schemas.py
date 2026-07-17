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
    price: float  # dollars (placeholder MVP pricing)

    model_config = {"from_attributes": True}


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
