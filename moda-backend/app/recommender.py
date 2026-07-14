"""MODA recommendation engine.

Core ideas
----------
1. Taste profile: quiz answers -> short natural-language phrases -> averaged
   CLIP text embedding (the "quiz anchor").
2. Adaptive blend: the live user embedding is
       user = alpha * quiz + beta * mean(liked) - gamma * mean(disliked)
   followed by L2 normalization. Saves count as strong likes.
3. Retrieval: pgvector cosine nearest-neighbor over outfit image embeddings,
   excluding anything the user has already interacted with.
4. Re-ranking: a light MMR (maximal marginal relevance) pass so the feed
   doesn't collapse into 20 near-identical outfits.
5. Explanations: tag overlap between the outfit and the user's taste profile.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.embeddings import embed_profile_phrases
from app.schemas import QuizSubmission

settings = get_settings()

# Saves signal stronger intent than likes; skips are a mild negative.
POSITIVE_WEIGHTS = {"like": 1.0, "save": 1.5}
NEGATIVE_WEIGHTS = {"dislike": 1.0, "skip": 0.25}


# ---------------------------------------------------------------------------
# Profile building
# ---------------------------------------------------------------------------

def build_profile_phrases(quiz: QuizSubmission) -> list[str]:
    """Turn quiz answers into short CLIP-friendly phrases.

    Kept deliberately plain: outfit embeddings blend 30% Unsplash-style
    captions, and an A/B against "a photo of …" prompt templates and
    aesthetic up-weighting showed plain equal-weight phrases retrieve more
    on-aesthetic outfits on this corpus.
    """
    phrases: list[str] = []
    for a in quiz.aesthetics:
        phrases.append(f"{a} style outfit")
    if quiz.colors:
        phrases.append(f"outfit in {', '.join(quiz.colors[:4])} colors")
    for fit in quiz.fits:
        phrases.append(f"{fit} fit clothing")
    for occ in quiz.occasions:
        phrases.append(f"outfit for {occ}")
    for brand in quiz.brands[:5]:
        phrases.append(f"{brand} style clothing")
    for insp in quiz.inspirations[:5]:
        phrases.append(f"fashion inspired by {insp}")
    return phrases or ["modern minimal everyday outfit"]


def build_profile_text(quiz: QuizSubmission) -> str:
    """Human-readable taste summary stored on the user."""
    parts = []
    if quiz.aesthetics:
        parts.append(" and ".join(quiz.aesthetics) + " aesthetics")
    if quiz.fits:
        parts.append(", ".join(quiz.fits) + " silhouettes")
    if quiz.colors:
        parts.append(", ".join(quiz.colors) + " palette")
    if quiz.occasions:
        parts.append("worn for " + ", ".join(quiz.occasions))
    if quiz.brands:
        parts.append("influenced by " + ", ".join(quiz.brands[:5]))
    return ("A taste profile centered on " + "; ".join(parts) + ".") if parts else (
        "A modern, minimal everyday taste profile."
    )


# ---------------------------------------------------------------------------
# User embedding blend
# ---------------------------------------------------------------------------

def _l2(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def decay_factor(created_at: datetime, now: datetime, half_life_days: float) -> float:
    """Exponential recency decay: an interaction half_life_days old counts 0.5x.

    half_life_days <= 0 disables decay (all interactions weigh equally).
    """
    if half_life_days <= 0:
        return 1.0
    age_days = max((now - created_at).total_seconds() / 86400.0, 0.0)
    return float(0.5 ** (age_days / half_life_days))


def _weighted_mean(
    db: Session, user_id: uuid.UUID, weights: dict[str, float]
) -> np.ndarray | None:
    rows = db.execute(
        select(
            models.Outfit.embedding,
            models.Interaction.interaction_type,
            models.Interaction.created_at,
        )
        .join(models.Interaction, models.Interaction.outfit_id == models.Outfit.id)
        .where(
            models.Interaction.user_id == user_id,
            models.Interaction.interaction_type.in_(list(weights)),
        )
    ).all()
    if not rows:
        return None
    now = datetime.now(timezone.utc)
    half_life = settings.feedback_half_life_days
    vecs = np.array([np.asarray(emb, dtype=np.float32) for emb, _, _ in rows])
    w = np.array(
        [weights[t] * decay_factor(ts, now, half_life) for _, t, ts in rows],
        dtype=np.float32,
    )[:, None]
    return (vecs * w).sum(axis=0) / w.sum()


def compute_user_embedding(db: Session, user: models.User) -> np.ndarray | None:
    """alpha*quiz + beta*mean(positives) - gamma*mean(negatives), normalized."""
    quiz_vec = (
        np.asarray(user.quiz_embedding, dtype=np.float32)
        if user.quiz_embedding is not None
        else None
    )
    pos = _weighted_mean(db, user.id, POSITIVE_WEIGHTS)
    neg = _weighted_mean(db, user.id, NEGATIVE_WEIGHTS)

    if quiz_vec is None and pos is None:
        return None

    dim = settings.embedding_dim
    blended = np.zeros(dim, dtype=np.float32)
    if quiz_vec is not None:
        blended += settings.alpha_quiz * quiz_vec
    if pos is not None:
        blended += settings.beta_liked * pos
    if neg is not None:
        blended -= settings.gamma_disliked * neg
    return _l2(blended)


def refresh_user_embedding(db: Session, user: models.User) -> bool:
    vec = compute_user_embedding(db, user)
    if vec is None:
        return False
    user.embedding = vec.tolist()
    db.add(user)
    return True


def apply_quiz(db: Session, user: models.User, quiz: QuizSubmission) -> str:
    phrases = build_profile_phrases(quiz)
    user.quiz_embedding = embed_profile_phrases(phrases).tolist()
    user.profile_text = build_profile_text(quiz)

    # Seed interactions from quiz-stage likes/dislikes
    for oid in quiz.liked_outfit_ids:
        db.merge(models.Interaction(user_id=user.id, outfit_id=oid, interaction_type="like"))
    for oid in quiz.disliked_outfit_ids:
        db.merge(models.Interaction(user_id=user.id, outfit_id=oid, interaction_type="dislike"))
    db.flush()

    refresh_user_embedding(db, user)
    return user.profile_text


# ---------------------------------------------------------------------------
# Retrieval + diversity re-ranking
# ---------------------------------------------------------------------------

def _seen_outfit_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(models.Interaction.outfit_id).where(models.Interaction.user_id == user_id)
        ).all()
    )


def retrieve_candidates(
    db: Session, user_vec: np.ndarray, exclude: list[uuid.UUID], pool_size: int
) -> list[tuple[models.Outfit, float]]:
    """Nearest-neighbor retrieval via pgvector cosine distance."""
    dist = models.Outfit.embedding.cosine_distance(user_vec.tolist())
    stmt = select(models.Outfit, dist.label("distance"))
    if exclude:
        stmt = stmt.where(models.Outfit.id.not_in(exclude))
    stmt = stmt.order_by(dist).limit(pool_size)
    rows = db.execute(stmt).all()
    # cosine similarity = 1 - cosine distance
    return [(outfit, float(1.0 - distance)) for outfit, distance in rows]


def mmr_rerank(
    candidates: list[tuple[models.Outfit, float]], k: int, lam: float
) -> list[tuple[models.Outfit, float]]:
    """Maximal marginal relevance: trade a little relevance for variety."""
    if lam <= 0 or len(candidates) <= k:
        return candidates[:k]

    embs = {c[0].id: _l2(np.asarray(c[0].embedding, dtype=np.float32)) for c in candidates}
    selected: list[tuple[models.Outfit, float]] = []
    remaining = list(candidates)

    while remaining and len(selected) < k:
        best, best_score = None, -np.inf
        for outfit, rel in remaining:
            if selected:
                max_sim = max(
                    float(embs[outfit.id] @ embs[s.id]) for s, _ in selected
                )
            else:
                max_sim = 0.0
            score = (1 - lam) * rel - lam * max_sim
            if score > best_score:
                best, best_score = (outfit, rel), score
        selected.append(best)
        remaining.remove(best)
    return selected


# ---------------------------------------------------------------------------
# Explanations
# ---------------------------------------------------------------------------

def _user_taste_tags(db: Session, user: models.User) -> set[str]:
    tags: set[str] = set()
    if user.profile_text:
        tags |= {w.strip(".,;").lower() for w in user.profile_text.split()}
    rows = db.execute(
        select(models.Outfit.style_tags, models.Outfit.color_tags, models.Outfit.occasion_tags)
        .join(models.Interaction, models.Interaction.outfit_id == models.Outfit.id)
        .where(
            models.Interaction.user_id == user.id,
            models.Interaction.interaction_type.in_(["like", "save"]),
        )
        .limit(50)
    ).all()
    for style, color, occasion in rows:
        tags |= {t.lower() for t in (style or []) + (color or []) + (occasion or [])}
    return tags


def _matched_tags(outfit: models.Outfit, taste_tags: set[str]) -> list[str]:
    """Outfit tags present in the user's taste vocabulary.

    Multi-word tags ("old money") match if every word appears — profile_text
    is tokenized word-by-word so the joined form is never in the set.
    """
    tags = (
        (outfit.style_tags or []) + (outfit.color_tags or []) + (outfit.occasion_tags or [])
    )
    out = []
    for t in tags:
        tl = t.lower()
        if tl in taste_tags or (" " in tl and all(w in taste_tags for w in tl.split())):
            out.append(t)
    return out


def tag_boost(outfit: models.Outfit, taste_tags: set[str]) -> float:
    """Small additive score bonus for matching the user's stated taste.

    CLIP cosine deltas across the catalog are ~0.05, so even two matched
    tags meaningfully lift on-aesthetic outfits without drowning the
    visual signal.
    """
    per_tag = settings.tag_affinity_boost
    return per_tag * min(len(_matched_tags(outfit, taste_tags)), 2)


def explain(outfit: models.Outfit, taste_tags: set[str]) -> str:
    outfit_tags = [
        t for t in (outfit.style_tags or []) + (outfit.color_tags or []) if t
    ]
    overlap = [t for t in outfit_tags if t.lower() in taste_tags]
    if len(overlap) >= 2:
        return f"Recommended because you like {overlap[0]} and {overlap[1]} pieces."
    if len(overlap) == 1:
        return f"Recommended because you like {overlap[0]} styles."
    if outfit_tags:
        return f"A close visual match to your taste profile, with {outfit_tags[0]} influences."
    return "A close visual match to your taste profile."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def recommend(db: Session, user: models.User, k: int) -> list[dict]:
    if user.embedding is None:
        raise ValueError("User has no embedding yet; submit the style quiz first.")

    user_vec = np.asarray(user.embedding, dtype=np.float32)
    seen = _seen_outfit_ids(db, user.id)
    taste_tags = _user_taste_tags(db, user)

    # Over-fetch so MMR has room to diversify
    candidates = retrieve_candidates(db, user_vec, seen, pool_size=max(k * 3, 30))
    # Hybrid score: visual similarity + stated-taste tag affinity
    candidates = sorted(
        ((o, s + tag_boost(o, taste_tags)) for o, s in candidates),
        key=lambda c: c[1],
        reverse=True,
    )
    ranked = mmr_rerank(candidates, k=k, lam=settings.diversity_lambda)

    return [
        {"outfit": outfit, "score": round(score, 4), "explanation": explain(outfit, taste_tags)}
        for outfit, score in ranked
    ]
