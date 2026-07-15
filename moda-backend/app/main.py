from contextlib import asynccontextmanager

import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, recommender, schemas
from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import get_settings
from app.db import get_db, init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MODA API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Health ----------

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Auth ----------

@app.post("/auth/signup", response_model=schemas.AuthOut, status_code=201)
def signup(payload: schemas.SignupIn, db: Session = Depends(get_db)):
    exists = db.scalar(
        select(models.User).where(
            (models.User.email == payload.email) | (models.User.username == payload.username)
        )
    )
    if exists:
        raise HTTPException(409, "Email or username already taken")
    user = models.User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(user.id), "user": user}


@app.post("/auth/login", response_model=schemas.AuthOut)
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == payload.email))
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_access_token(user.id), "user": user}


@app.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


# ---------- Quiz ----------

@app.post("/quiz", response_model=schemas.QuizResult)
def submit_quiz(
    payload: schemas.QuizSubmission,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_text = recommender.apply_quiz(db, user, payload)
    db.commit()
    return schemas.QuizResult(user_id=user.id, profile_text=profile_text)


# ---------- Recommendations ----------

@app.get("/recommendations", response_model=schemas.FeedOut)
def get_recommendations(
    k: int = settings.default_feed_size,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        items = recommender.recommend(db, user, k=min(k, 100))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"user_id": user.id, "items": items}


# ---------- Feedback ----------

@app.post("/feedback", response_model=schemas.FeedbackOut)
def submit_feedback(
    payload: schemas.FeedbackIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.get(models.Outfit, payload.outfit_id):
        raise HTTPException(404, "Outfit not found")

    existing = db.scalar(
        select(models.Interaction).where(
            models.Interaction.user_id == user.id,
            models.Interaction.outfit_id == payload.outfit_id,
            models.Interaction.interaction_type == payload.interaction_type,
        )
    )
    if not existing:
        db.add(
            models.Interaction(
                user_id=user.id,
                outfit_id=payload.outfit_id,
                interaction_type=payload.interaction_type,
            )
        )
        db.flush()

    # Skips don't move the taste vector enough to justify a recompute on every event
    updated = False
    if payload.interaction_type in ("like", "dislike", "save"):
        updated = recommender.refresh_user_embedding(db, user)

    db.commit()
    return {"ok": True, "interaction_type": payload.interaction_type, "user_embedding_updated": updated}


# ---------- Saved outfits ----------

@app.get("/saved", response_model=list[schemas.OutfitOut])
def get_saved(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(models.Outfit)
        .join(models.Interaction, models.Interaction.outfit_id == models.Outfit.id)
        .where(
            models.Interaction.user_id == user.id,
            models.Interaction.interaction_type == "save",
        )
        .order_by(models.Interaction.created_at.desc())
    ).all()
    return rows


# ---------- Outfits ----------

@app.get("/outfits/sample", response_model=list[schemas.OutfitOut])
def sample_outfits(
    n: int = 12,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """A visually diverse sample for quiz-time taste calibration.

    Random pool, then MMR with relevance held constant — which reduces to
    picking maximally spread-out embeddings.
    """
    n = min(max(n, 1), 24)
    pool = db.scalars(
        select(models.Outfit).order_by(func.random()).limit(n * 4)
    ).all()
    picked = recommender.mmr_rerank([(o, 1.0) for o in pool], k=n, lam=0.7)
    return [o for o, _ in picked]


@app.get("/outfits/{outfit_id}", response_model=schemas.OutfitOut)
def get_outfit(outfit_id: uuid.UUID, db: Session = Depends(get_db)):
    outfit = db.get(models.Outfit, outfit_id)
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    return outfit


@app.get("/outfits/{outfit_id}/items", response_model=list[schemas.ItemOut])
def get_outfit_items(outfit_id: uuid.UUID, db: Session = Depends(get_db)):
    """Shop the look: visually similar purchasable pieces for an outfit."""
    if not db.get(models.Outfit, outfit_id):
        raise HTTPException(404, "Outfit not found")
    rows = db.scalars(
        select(models.Item)
        .join(models.OutfitItem, models.OutfitItem.item_id == models.Item.id)
        .where(models.OutfitItem.outfit_id == outfit_id)
        .order_by(models.OutfitItem.rank)
    ).all()
    return rows


# ---------- Items ----------

@app.get("/items/recommended", response_model=list[schemas.ItemOut])
def recommended_items(
    k: int = 24,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pieces ranked by the user's taste vector."""
    if user.embedding is None:
        raise HTTPException(400, "User has no embedding yet; submit the style quiz first.")
    k = min(max(k, 1), 100)
    dist = models.Item.embedding.cosine_distance(list(user.embedding))
    return db.scalars(select(models.Item).order_by(dist).limit(k)).all()


@app.get("/items", response_model=list[schemas.ItemOut])
def list_items(
    k: int = 24,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """Browse the item catalog (unpersonalized)."""
    k = min(max(k, 1), 100)
    stmt = select(models.Item)
    if category:
        stmt = stmt.where(models.Item.category == category)
    return db.scalars(stmt.order_by(func.random()).limit(k)).all()


@app.get("/items/{item_id}", response_model=schemas.ItemOut)
def get_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    return item
