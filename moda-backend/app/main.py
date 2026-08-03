from contextlib import asynccontextmanager

import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import catalog, models, payments, payouts, recommender, schemas
from app.auth import (
    create_access_token,
    get_current_admin,
    get_current_seller,
    get_current_user,
    hash_password,
    verify_password,
)
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
        .where(models.OutfitItem.outfit_id == outfit_id, _approved())
        .order_by(models.OutfitItem.rank)
    ).all()
    return rows


# ---------- Items ----------

def _approved():
    """Shoppers only ever see approved listings."""
    return models.Item.status == models.ITEM_APPROVED


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
    return db.scalars(select(models.Item).where(_approved()).order_by(dist).limit(k)).all()


@app.get("/items", response_model=list[schemas.ItemOut])
def list_items(
    k: int = 24,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """Browse the item catalog (unpersonalized)."""
    k = min(max(k, 1), 100)
    stmt = select(models.Item).where(_approved())
    if category:
        stmt = stmt.where(models.Item.category == category)
    return db.scalars(stmt.order_by(func.random()).limit(k)).all()


@app.get("/items/{item_id}", response_model=schemas.ItemOut)
def get_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(models.Item, item_id)
    if not item or item.status != models.ITEM_APPROVED:
        raise HTTPException(404, "Item not found")
    return item


# ---------- Seller ----------

def _embed_listing_or_400(image_url: str, name: str, caption: str | None) -> list[float]:
    try:
        url = catalog.validate_listing_image_url(image_url)
        return catalog.embed_listing(catalog.load_image(url), name, caption)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, "Could not load that image URL — check it's a public direct link")


@app.post("/seller/upgrade", response_model=schemas.SellerOut)
def become_seller(
    payload: schemas.SellerUpgradeIn,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Turn any account into a seller by claiming a brand name."""
    brand = payload.brand_name.strip()
    taken = db.scalar(
        select(models.User).where(
            func.lower(models.User.brand_name) == brand.lower(),
            models.User.id != user.id,
        )
    )
    if taken:
        raise HTTPException(409, "That brand name is already taken")
    user.is_seller = True
    user.brand_name = brand
    db.commit()
    db.refresh(user)
    return user


@app.get("/seller/me", response_model=schemas.SellerOut)
def seller_me(user: models.User = Depends(get_current_user)):
    return user


@app.get("/seller/listings", response_model=list[schemas.ListingOut])
def my_listings(
    seller: models.User = Depends(get_current_seller), db: Session = Depends(get_db)
):
    return db.scalars(
        select(models.Item)
        .where(
            models.Item.seller_id == seller.id,
            models.Item.status != models.ITEM_REMOVED,
        )
        .order_by(models.Item.created_at.desc())
    ).all()


@app.post("/seller/listings", response_model=schemas.ListingOut, status_code=201)
def create_listing(
    payload: schemas.ListingIn,
    seller: models.User = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    """Create a listing. It enters the queue as `pending` until reviewed."""
    embedding = _embed_listing_or_400(payload.image_url, payload.name, payload.caption)
    item = models.Item(
        name=payload.name.strip(),
        category=payload.category.strip().lower(),
        image_url=payload.image_url.strip(),
        caption=(payload.caption or "").strip() or None,
        style_tags=[t.strip().lower() for t in payload.style_tags if t.strip()],
        color_tags=[t.strip().lower() for t in payload.color_tags if t.strip()],
        price_cents=round(payload.price * 100),
        embedding=embedding,
        seller_id=seller.id,
        status=models.ITEM_PENDING,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _own_listing(db: Session, listing_id: uuid.UUID, seller: models.User) -> models.Item:
    item = db.get(models.Item, listing_id)
    if not item or item.seller_id != seller.id or item.status == models.ITEM_REMOVED:
        raise HTTPException(404, "Listing not found")
    return item


@app.patch("/seller/listings/{listing_id}", response_model=schemas.ListingOut)
def update_listing(
    listing_id: uuid.UUID,
    payload: schemas.ListingUpdate,
    seller: models.User = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    item = _own_listing(db, listing_id, seller)

    if payload.image_url and payload.image_url.strip() != item.image_url:
        # New photo means new visual content: re-embed and re-review
        item.image_url = payload.image_url.strip()
        item.embedding = _embed_listing_or_400(
            item.image_url, payload.name or item.name, payload.caption or item.caption
        )
        item.status = models.ITEM_PENDING
        item.review_note = None
    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.category is not None:
        item.category = payload.category.strip().lower()
    if payload.caption is not None:
        item.caption = payload.caption.strip() or None
    if payload.price is not None:
        item.price_cents = round(payload.price * 100)
    if payload.style_tags is not None:
        item.style_tags = [t.strip().lower() for t in payload.style_tags if t.strip()]
    if payload.color_tags is not None:
        item.color_tags = [t.strip().lower() for t in payload.color_tags if t.strip()]

    # A rejected listing goes back in the queue once the seller edits it
    if item.status == models.ITEM_REJECTED:
        item.status = models.ITEM_PENDING
        item.review_note = None

    db.commit()
    db.refresh(item)
    return item


@app.delete("/seller/listings/{listing_id}", status_code=204)
def remove_listing(
    listing_id: uuid.UUID,
    seller: models.User = Depends(get_current_seller),
    db: Session = Depends(get_db),
):
    """Soft delete: order history and carts reference items by id."""
    item = _own_listing(db, listing_id, seller)
    item.status = models.ITEM_REMOVED
    db.execute(delete(models.CartItem).where(models.CartItem.item_id == item.id))
    db.execute(delete(models.OutfitItem).where(models.OutfitItem.item_id == item.id))
    db.commit()


# ---------- Moderation ----------

@app.get("/admin/listings", response_model=list[schemas.ListingOut])
def review_queue(
    status: str = models.ITEM_PENDING,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if status not in models.ITEM_STATUSES:
        raise HTTPException(400, f"status must be one of {', '.join(models.ITEM_STATUSES)}")
    return db.scalars(
        select(models.Item)
        .where(models.Item.status == status, models.Item.seller_id.is_not(None))
        .order_by(models.Item.created_at)
    ).all()


@app.post("/admin/listings/{listing_id}/approve", response_model=schemas.ListingOut)
def approve_listing(
    listing_id: uuid.UUID,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    item = db.get(models.Item, listing_id)
    if not item or item.seller_id is None:
        raise HTTPException(404, "Listing not found")
    item.status = models.ITEM_APPROVED
    item.review_note = None
    db.commit()
    db.refresh(item)
    return item


@app.post("/admin/listings/{listing_id}/reject", response_model=schemas.ListingOut)
def reject_listing(
    listing_id: uuid.UUID,
    payload: schemas.ReviewIn,
    admin: models.User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    item = db.get(models.Item, listing_id)
    if not item or item.seller_id is None:
        raise HTTPException(404, "Listing not found")
    item.status = models.ITEM_REJECTED
    item.review_note = (payload.note or "").strip() or None
    # Pull it from any cart it slipped into while approved
    db.execute(delete(models.CartItem).where(models.CartItem.item_id == item.id))
    db.commit()
    db.refresh(item)
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
    item = db.get(models.Item, payload.item_id)
    if not item or item.status != models.ITEM_APPROVED:
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
    result = payments.charge(total)
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
                seller_id=line.item.seller_id,
            )
        )
        db.delete(line)

    _create_payouts(db, order, lines)
    db.commit()
    db.refresh(order)
    return order


def _create_payouts(db: Session, order: models.Order, lines: list[models.CartItem]) -> None:
    """Split the order per seller and attempt each transfer.

    A seller who hasn't finished onboarding still gets a payout row — it
    stays `pending` and is settled by `POST /seller/payouts/retry` once
    they're verified, which mirrors Stripe holding funds.
    """
    settings_ = get_settings()
    splits = payouts.split_order(
        [(l.item.seller_id, l.item.price_cents, l.qty) for l in lines],
        fee_bps=settings_.platform_fee_bps,
    )
    for split in splits:
        seller = db.get(models.User, split.seller_id)
        payout = models.Payout(
            order_id=order.id,
            seller_id=split.seller_id,
            gross_cents=split.gross_cents,
            fee_cents=split.fee_cents,
            net_cents=split.net_cents,
            provider=payments.active_provider(),
            status=models.PAYOUT_PENDING,
        )
        db.add(payout)
        _attempt_transfer(payout, seller, order)


def _attempt_transfer(
    payout: models.Payout, seller: models.User | None, order: models.Order
) -> None:
    """Move a pending payout to paid/failed. Safe to call repeatedly."""
    if payout.status == models.PAYOUT_PAID:
        return
    if not seller or not seller.payouts_enabled or not seller.stripe_account_id:
        payout.failure_reason = "Seller has not completed payout onboarding"
        return

    result = payments.transfer(
        payout.net_cents, seller.stripe_account_id, str(order.id)
    )
    if result.ok:
        payout.status = models.PAYOUT_PAID
        payout.transfer_ref = result.ref
        payout.paid_at = models.utcnow()
        payout.failure_reason = None
    else:
        payout.status = models.PAYOUT_FAILED
        payout.failure_reason = result.message or "Transfer failed"


# ---------- Seller payouts ----------

def _payout_totals(db: Session, seller_id: uuid.UUID) -> tuple[int, int]:
    """(pending net, paid net) in cents."""
    rows = db.execute(
        select(models.Payout.status, func.sum(models.Payout.net_cents))
        .where(models.Payout.seller_id == seller_id)
        .group_by(models.Payout.status)
    ).all()
    by_status = {status: int(total or 0) for status, total in rows}
    pending = by_status.get(models.PAYOUT_PENDING, 0) + by_status.get(
        models.PAYOUT_FAILED, 0
    )
    return pending, by_status.get(models.PAYOUT_PAID, 0)


@app.get("/seller/payouts/status", response_model=schemas.PayoutStatusOut)
def payout_status(
    seller: models.User = Depends(get_current_seller), db: Session = Depends(get_db)
):
    # Stripe is the source of truth for verification state
    if seller.stripe_account_id and not seller.payouts_enabled:
        if payments.account_payouts_enabled(seller.stripe_account_id):
            seller.payouts_enabled = True
            db.commit()

    pending, paid = _payout_totals(db, seller.id)
    provider = payments.active_provider()
    return schemas.PayoutStatusOut(
        onboarding_started=seller.stripe_account_id is not None,
        payouts_enabled=seller.payouts_enabled,
        provider=provider,
        simulated=provider == "mock",
        pending_cents=pending,
        paid_cents=paid,
    )


@app.post("/seller/payouts/onboard", response_model=schemas.OnboardingOut)
def start_payout_onboarding(
    seller: models.User = Depends(get_current_seller), db: Session = Depends(get_db)
):
    """Create the connected account (once) and return a hosted onboarding link."""
    if not seller.stripe_account_id:
        account = payments.create_connect_account(seller.email, seller.brand_name)
        if not account.ok:
            raise HTTPException(502, f"Could not start onboarding: {account.message}")
        seller.stripe_account_id = account.account_id
        db.commit()

    base = get_settings().app_base_url.rstrip("/")
    link = payments.onboarding_link(
        seller.stripe_account_id,
        return_url=f"{base}/sell?payouts=done",
        refresh_url=f"{base}/sell?payouts=retry",
    )
    if not link.ok:
        raise HTTPException(502, f"Could not start onboarding: {link.message}")

    if link.simulated:
        # No hosted page to visit — mark ready so the flow is exercisable
        seller.payouts_enabled = True
        db.commit()

    return schemas.OnboardingOut(
        ok=True,
        url=link.url,
        simulated=link.simulated,
        payouts_enabled=seller.payouts_enabled,
    )


@app.post("/seller/payouts/retry", response_model=list[schemas.PayoutOut])
def retry_payouts(
    seller: models.User = Depends(get_current_seller), db: Session = Depends(get_db)
):
    """Settle everything owed — used after onboarding completes."""
    if seller.stripe_account_id and not seller.payouts_enabled:
        seller.payouts_enabled = payments.account_payouts_enabled(seller.stripe_account_id)

    outstanding = db.scalars(
        select(models.Payout).where(
            models.Payout.seller_id == seller.id,
            models.Payout.status.in_([models.PAYOUT_PENDING, models.PAYOUT_FAILED]),
        )
    ).all()
    for payout in outstanding:
        payout.status = models.PAYOUT_PENDING
        _attempt_transfer(payout, seller, payout.order)
    db.commit()
    return outstanding


@app.get("/seller/earnings", response_model=schemas.EarningsOut)
def seller_earnings(
    seller: models.User = Depends(get_current_seller), db: Session = Depends(get_db)
):
    rows = db.scalars(
        select(models.Payout)
        .where(models.Payout.seller_id == seller.id)
        .order_by(models.Payout.created_at.desc())
    ).all()
    pending, _ = _payout_totals(db, seller.id)
    return schemas.EarningsOut(
        brand_name=seller.brand_name,
        payouts_enabled=seller.payouts_enabled,
        lifetime_gross=sum(p.gross_cents for p in rows) / 100,
        lifetime_fees=sum(p.fee_cents for p in rows) / 100,
        lifetime_net=sum(p.net_cents for p in rows) / 100,
        pending_net=pending / 100,
        payouts=rows,
    )


@app.get("/orders", response_model=list[schemas.OrderOut])
def list_orders(
    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.scalars(
        select(models.Order)
        .where(models.Order.user_id == user.id)
        .order_by(models.Order.created_at.desc())
    ).all()
