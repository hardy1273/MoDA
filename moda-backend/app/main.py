from contextlib import asynccontextmanager

import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, payments, recommender, schemas
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


# ---------- Impressions ----------

@app.post("/impressions", status_code=204)
def record_impressions(
    payload: schemas.ImpressionsIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch-record that outfits were shown (fired by the feed on render)."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import utcnow

    # Only known outfits: a stale/bogus id must not 500 the whole batch
    valid_ids = set(
        db.scalars(
            select(models.Outfit.id).where(models.Outfit.id.in_(set(payload.outfit_ids)))
        ).all()
    )
    if not valid_ids:
        return

    now = utcnow()
    stmt = pg_insert(models.Impression).values(
        [
            # id set explicitly: bulk INSERT bypasses the ORM-side uuid default
            {"id": uuid.uuid4(), "user_id": user.id, "outfit_id": oid, "count": 1, "last_seen_at": now}
            for oid in valid_ids
        ]
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_impression",
        set_={"count": models.Impression.count + 1, "last_seen_at": now},
    )
    db.execute(stmt)
    db.commit()


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


# ---------- Cart ----------

def _cart_lines(db: Session, user_id: uuid.UUID) -> list[models.CartItem]:
    return list(
        db.scalars(
            select(models.CartItem)
            .where(models.CartItem.user_id == user_id)
            .order_by(models.CartItem.created_at)
        ).all()
    )


def cart_total_cents(lines: list[models.CartItem]) -> int:
    return sum(line.item.price_cents * line.qty for line in lines)


def _cart_out(lines: list[models.CartItem]) -> dict:
    return {"items": lines, "total": cart_total_cents(lines) / 100}


@app.get("/cart", response_model=schemas.CartOut)
def get_cart(
    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return _cart_out(_cart_lines(db, user.id))


@app.post("/cart/items", response_model=schemas.CartOut)
def add_cart_line(
    payload: schemas.CartLineIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.get(models.Item, payload.item_id):
        raise HTTPException(404, "Item not found")
    line = db.scalar(
        select(models.CartItem).where(
            models.CartItem.user_id == user.id,
            models.CartItem.item_id == payload.item_id,
            models.CartItem.size == payload.size,
        )
    )
    if line:
        line.qty = min(line.qty + payload.qty, 20)
    else:
        db.add(
            models.CartItem(
                user_id=user.id, item_id=payload.item_id, size=payload.size, qty=payload.qty
            )
        )
    db.commit()
    return _cart_out(_cart_lines(db, user.id))


@app.patch("/cart/items/{line_id}", response_model=schemas.CartOut)
def update_cart_line(
    line_id: uuid.UUID,
    payload: schemas.CartLineQty,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    line = db.get(models.CartItem, line_id)
    if not line or line.user_id != user.id:
        raise HTTPException(404, "Cart line not found")
    if payload.qty == 0:
        db.delete(line)
    else:
        line.qty = payload.qty
    db.commit()
    return _cart_out(_cart_lines(db, user.id))


@app.delete("/cart/items/{line_id}", response_model=schemas.CartOut)
def remove_cart_line(
    line_id: uuid.UUID,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    line = db.get(models.CartItem, line_id)
    if not line or line.user_id != user.id:
        raise HTTPException(404, "Cart line not found")
    db.delete(line)
    db.commit()
    return _cart_out(_cart_lines(db, user.id))


# ---------- Checkout / Orders ----------

@app.post("/checkout", response_model=schemas.OrderOut)
def checkout(
    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Charge the cart (mock provider) and turn it into an order.

    Totals and line prices come from the items table server-side; the
    order snapshots name/price/image so history survives catalog edits.
    """
    lines = _cart_lines(db, user.id)
    if not lines:
        raise HTTPException(400, "Cart is empty")

    total = cart_total_cents(lines)
    result = payments.charge(total, provider="mock")
    if not result.ok:
        raise HTTPException(402, result.message or "Payment failed")

    order = models.Order(
        user_id=user.id,
        status="paid",
        total_cents=total,
        payment_provider=result.provider,
        payment_ref=result.ref,
    )
    db.add(order)
    db.flush()
    for line in lines:
        db.add(
            models.OrderItem(
                order_id=order.id,
                item_id=line.item_id,
                name=line.item.name,
                image_url=line.item.image_url,
                price_cents=line.item.price_cents,
                size=line.size,
                qty=line.qty,
            )
        )
        db.delete(line)
    db.commit()
    db.refresh(order)
    return order


@app.get("/orders", response_model=list[schemas.OrderOut])
def list_orders(
    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.scalars(
        select(models.Order)
        .where(models.Order.user_id == user.id)
        .order_by(models.Order.created_at.desc())
    ).all()
