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
    # Additive score bonus per outfit tag matching the user's taste (max 2 tags).
    # 0.15 since tags became image-derived (scripts/retag.py) and therefore
    # trustworthy; the old 0.05 was tuned for noisy query-derived tags. Higher
    # values change nothing — the effect saturates here.
    tag_affinity_boost: float = 0.15
    # Score penalty per prior impression (capped at 5 views) — feed fatigue
    impression_penalty: float = 0.02

    # Auth — override jwt_secret in .env for anything beyond local dev
    jwt_secret: str = "dev-only-jwt-secret-change-me-for-production-use"
    jwt_expires_minutes: int = 60 * 24 * 7  # 7 days

    # Payments & payouts. Empty stripe_secret_key => simulated provider,
    # which still exercises the whole onboarding/payout flow locally.
    stripe_secret_key: str = ""
    # From `stripe listen` locally, or the dashboard endpoint in production
    stripe_webhook_secret: str = ""
    currency: str = "usd"
    # Platform commission in basis points (1000 = 10%)
    platform_fee_bps: int = 1000
    # Where Stripe sends sellers back after hosted onboarding
    app_base_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
