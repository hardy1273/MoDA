from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://moda:moda@localhost:5432/moda"

    clip_model: str = "ViT-B-32"
    clip_pretrained: str = "laion2b_s34b_b79k"
    embedding_dim: int = 512

    alpha_quiz: float = 0.5
    beta_liked: float = 0.4
    gamma_disliked: float = 0.2

    default_feed_size: int = 20
    diversity_lambda: float = 0.3
    # Recency half-life for like/dislike/save weighting; <= 0 disables decay
    feedback_half_life_days: float = 14.0
    # Additive score bonus per outfit tag matching the user's taste (max 2 tags)
    tag_affinity_boost: float = 0.05

    # Auth — override jwt_secret in .env for anything beyond local dev
    jwt_secret: str = "dev-only-jwt-secret-change-me-for-production-use"
    jwt_expires_minutes: int = 60 * 24 * 7  # 7 days


@lru_cache
def get_settings() -> Settings:
    return Settings()
