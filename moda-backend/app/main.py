import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, recommender, schemas
from app.config import get_settings
from app.db import get_db, init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MODA API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_user(db: Session, user_id: uuid.UUID) -> models.User:
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user


# ---------- Health ----------

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Users ----------

@app.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    exists = db.scalar(
        select(models.User).where(
            (models.User.email == payload.email) | (models.User.username == payload.username)
        )
    )
    if exists:
        raise HTTPException(409, "Email or username already taken")
    user = models.User(email=payload.email, username=payload.username)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users/{user_id}", response_model=schemas.UserOut)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    return _get_user(db, user_id)


# ---------- Quiz ----------

@app.post("/quiz", response_model=schemas.QuizResult)
def submit_quiz(payload: schemas.QuizSubmission, db: Session = Depends(get_db)):
    user = _get_user(db, payload.user_id)
    profile_text = recommender.apply_quiz(db, user, payload)
    db.commit()
    return schemas.QuizResult(user_id=user.id, profile_text=profile_text)


# ---------- Recommendations ----------

@app.get("/recommendations", response_model=schemas.FeedOut)
def get_recommendations(
    user_id: uuid.UUID,
    k: int = settings.default_feed_size,
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_id)
    try:
        items = recommender.recommend(db, user, k=min(k, 100))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"user_id": user.id, "items": items}


# ---------- Feedback ----------

@app.post("/feedback", response_model=schemas.FeedbackOut)
def submit_feedback(payload: schemas.FeedbackIn, db: Session = Depends(get_db)):
    user = _get_user(db, payload.user_id)
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
def get_saved(user_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_user(db, user_id)
    rows = db.scalars(
        select(models.Outfit)
        .join(models.Interaction, models.Interaction.outfit_id == models.Outfit.id)
        .where(
            models.Interaction.user_id == user_id,
            models.Interaction.interaction_type == "save",
        )
        .order_by(models.Interaction.created_at.desc())
    ).all()
    return rows


# ---------- Outfits ----------

@app.get("/outfits/{outfit_id}", response_model=schemas.OutfitOut)
def get_outfit(outfit_id: uuid.UUID, db: Session = Depends(get_db)):
    outfit = db.get(models.Outfit, outfit_id)
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    return outfit
