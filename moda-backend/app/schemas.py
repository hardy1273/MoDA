import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------- Users ----------

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    username: str
    profile_text: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Quiz ----------

class QuizSubmission(BaseModel):
    user_id: uuid.UUID
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


# ---------- Feedback ----------

class FeedbackIn(BaseModel):
    user_id: uuid.UUID
    outfit_id: uuid.UUID
    interaction_type: str = Field(pattern="^(like|dislike|save|skip)$")


class FeedbackOut(BaseModel):
    ok: bool
    interaction_type: str
    user_embedding_updated: bool
