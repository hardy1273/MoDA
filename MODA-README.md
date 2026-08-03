# MODA Backend — Recommendation Engine MVP

AI-powered fashion recommendation backend. "Spotify Discover Weekly, but for fashion."

**Stack:** FastAPI · PostgreSQL + pgvector · Marqo-FashionCLIP (OpenCLIP) · SQLAlchemy 2.0

## How it works

1. **Quiz → taste anchor.** Quiz answers become short CLIP-friendly phrases
   ("minimal style outfit", "oversized fit clothing"), each embedded with
   OpenCLIP's text encoder and averaged into a 512-dim `quiz_embedding`.
   (Plain equal-weight phrases beat "a photo of …" templates and aesthetic
   up-weighting in an A/B on this corpus.) Quiz-time "pick the looks you
   love" calibration picks seed like interactions, anchoring taste in image
   space from the first feed.
2. **Outfits → image embeddings.** Each curated image is embedded with the
   same CLIP model's image encoder, so text taste and image outfits live in
   one shared vector space.
3. **Adaptive blend.** The live user vector is recomputed on every
   like/dislike/save:

   ```
   user = α·quiz + β·mean(liked ∪ saved) − γ·mean(disliked ∪ skipped)
   ```

   (saves weighted 1.5× a like, skips 0.25× a dislike; each interaction also
   decays with a `FEEDBACK_HALF_LIFE_DAYS` half-life so recent taste counts
   more; result L2-normalized)
4. **Retrieval + hybrid scoring.** pgvector cosine nearest-neighbor over
   outfit embeddings, excluding everything already seen, over-fetching 5×.
   Each candidate gets a small tag-affinity bonus (`TAG_AFFINITY_BOOST` per
   outfit tag matching the user's stated taste, max 2) — in testing this
   roughly doubled on-aesthetic items in the top 10 — and a fatigue penalty
   (`IMPRESSION_PENALTY` per prior view, capped at 5; the feed posts
   impressions on render). Then MMR re-ranking so the feed stays varied
   instead of 20 near-duplicates.
5. **Explanations.** Tag overlap between the outfit and the user's liked
   tags/profile produces the "Recommended because…" line.

## Quick start

```bash
# 1. Database
docker compose up -d

# 2. Python env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # or requirements-dev.txt for tests/migrations
cp .env.example .env

# 3. Ingest your curated images (see Dataset section)
python -m scripts.ingest --csv data/outfits.csv --blend-caption

# 4. Run the API
uvicorn app.main:app --reload

# 5. Smoke test the full loop
python -m scripts.smoke_test
```

Interactive docs: http://localhost:8000/docs

First quiz/ingest call downloads the CLIP weights (~600MB) once.

## API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/signup` | — | `{email, username, password}` → JWT + user |
| POST | `/auth/login` | — | `{email, password}` → JWT + user |
| GET | `/me` | Bearer | Current user |
| POST | `/quiz` | Bearer | Submit style quiz → builds taste profile + embedding |
| GET | `/recommendations?k=20` | Bearer | Personalized feed with scores + explanations |
| POST | `/feedback` | Bearer | `{outfit_id, interaction_type: like\|dislike\|save\|skip}` |
| GET | `/saved` | Bearer | Saved outfits |
| GET | `/outfits/sample?n=12` | Bearer | Visually diverse sample (quiz calibration) |
| GET | `/outfits/{id}` | — | Single outfit |
| GET | `/outfits/{id}/items` | — | Shop the look: similar purchasable pieces |
| GET | `/items` | — | Browse item catalog (`?category=`, `?k=`) |
| GET | `/items/recommended?k=` | Bearer | Pieces ranked by the user's taste vector |
| GET | `/items/{id}` | — | Single item |
| POST | `/seller/upgrade` | Bearer | Claim a brand name → seller account |
| GET | `/seller/me` | Bearer | Account flags (is_seller, brand, is_admin) |
| GET/POST | `/seller/listings` | Seller | List / create listings (new ones are `pending`) |
| PATCH/DELETE | `/seller/listings/{id}` | Seller | Edit / soft-remove a listing |
| GET | `/admin/listings?status=` | Moderator | Review queue |
| POST | `/admin/listings/{id}/approve\|reject` | Moderator | Moderate a listing |
| GET | `/seller/payouts/status` | Seller | Onboarding state + pending/paid totals |
| POST | `/seller/payouts/onboard` | Seller | Start Stripe Connect onboarding |
| POST | `/seller/payouts/retry` | Seller | Settle everything outstanding |
| GET | `/seller/earnings` | Seller | Lifetime totals + payout history |
| GET | `/payments/config` | — | Whether payment is real or simulated |
| POST | `/checkout` | Bearer | Start payment (redirect or simulated) |
| POST | `/checkout/confirm` | Bearer | Finalize after returning from Stripe |
| POST | `/webhooks/stripe` | Signature | Stripe's own confirmation |
| GET | `/health` | — | Liveness |

Items are individual pieces (hoodie, sneakers, …) with their own CLIP
embeddings. Seeded catalog items carry placeholder prices (deterministic per
item within a realistic category range); seller listings carry real ones.
Seeding pipeline: `scripts/fetch_items.py` → `scripts/ingest_items.py` →
`scripts/link_items.py` (links each outfit to its closest items, one per
category).

## Sellers & moderation

Any account becomes a seller by claiming a brand name — no separate signup.
Listings are embedded on creation (same vector space as the seeded catalog,
so they're recommendable immediately) and enter the queue as `pending`;
only `approved` items appear in `/items`, `/items/recommended`,
shop-the-look, and the cart. Rejection carries a note back to the seller, and
editing a rejected listing (or swapping its photo) returns it to the queue.
Deletes are soft (`removed`) because order history references items.

Grant yourself moderator access to work the queue:

```bash
python -m scripts.grant_admin --email you@example.com
python -m scripts.grant_admin --list
```

Listings take an image **URL**. The API fetching seller-supplied URLs is an
SSRF vector — production should upload from the browser to object storage, or
fetch through an egress proxy (`app/catalog.py` validates the scheme only).

## Payouts (Stripe Connect)

One cart can hold pieces from several sellers plus platform-owned seeded
stock, so a single charge fans out into one transfer per seller. At checkout
the order is split by seller (`app/payouts.py`), the platform commission
(`PLATFORM_FEE_BPS`, default 10%) is deducted, and a `payouts` row is written
per seller.

A seller who hasn't finished onboarding still gets a payout row — it stays
`pending` and settles via `POST /seller/payouts/retry` once they're verified,
mirroring how Stripe holds funds. Fees are computed on each seller's combined
gross, not per line, so repeated rounding can't nibble at their earnings;
`fee_cents + net_cents == gross_cents` always holds exactly.

Connect uses **Express** accounts (Stripe hosts onboarding and identity
verification) with **separate charges and transfers**. With
`STRIPE_SECRET_KEY` unset the provider is simulated: onboarding completes
instantly, transfers return fake references, and every response carries
`simulated: true` — so the whole marketplace flow is exercisable locally.

## Taking payment

Buyers pay through a **hosted Stripe Checkout** page, so card details never
touch this server and the app stays out of PCI scope.

```
POST /checkout            -> {mode: "redirect", url}  (Stripe configured)
                          -> {mode: "simulated", order}  (no key)
   buyer pays on Stripe, returns to /cart?session_id=...
POST /checkout/confirm    -> creates the order, idempotently
POST /webhooks/stripe     -> same, for buyers who close the tab
```

Because payment happens off-server, the order is created *after* confirmation,
and two things guard the gap:

- `orders.payment_session_id` is **unique**, so the return URL and the webhook
  racing each other can only ever produce one order (the loser catches the
  integrity error and returns the winner's).
- Cart lines are locked to the in-flight session via
  `cart_items.checkout_session_id`, so editing the cart in another tab mid-payment
  can't change what was actually bought.

Payment status is read back from Stripe, never trusted from the returning
browser. With no key configured the sale is simulated and the order is created
immediately — `GET /payments/config` tells the UI which it is, so the checkout
screen never implies a real charge.

For webhooks locally:

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
# paste the printed signing secret into STRIPE_WEBHOOK_SECRET
```

Transfers to sellers assume the platform balance is funded (in test mode,
fund it with test-card charges).

Protected routes take `Authorization: Bearer <token>`; tokens are HS256 JWTs
signed with `JWT_SECRET` (set a real value outside local dev).

Example quiz payload:

```json
{
  "aesthetics": ["minimal", "streetwear", "monochrome"],
  "colors": ["black", "white", "grey"],
  "fits": ["oversized", "tailored"],
  "occasions": ["everyday", "nightlife"],
  "brands": [],
  "inspirations": []
}
```

## Dataset (curated real images)

Ingestion takes a CSV (`data/outfits.sample.csv` is a template):

```
image,caption,style_tags,color_tags,occasion_tags
images/fit_001.jpg,"Neutral oversized minimal streetwear outfit…",streetwear|minimal,black|neutral,everyday
```

Practical guidance for curating:

- **Target 300–1000 images for a convincing MVP.** Below ~200, every user
  sees roughly the same feed regardless of taste.
- **Cover the aesthetic axes in your quiz** (streetwear, minimal, old money,
  techwear, etc.) with at least 30–50 images each, or recommendations for
  that aesthetic will be weak.
- **Single subject, full outfit visible, clean-ish background.** CLIP
  embeddings degrade on collages, heavy text overlays, and crowded scenes.
  `--blend-caption` partially compensates.
- **Captions matter** if you blend: keep them short, concrete, and visual
  ("black cargo pants with utility jacket"), not poetic.
- **Licensing:** for anything beyond local testing, stick to images you have
  rights to — Unsplash/Pexels fashion photography, brand press kits, or
  creator partnerships. Scraping Pinterest/Instagram for a public demo is a
  takedown (and ToS) risk.

## Tuning

All knobs live in `.env`:

- `ALPHA_QUIZ / BETA_LIKED / GAMMA_DISLIKED` — how fast taste drifts from the
  quiz anchor toward behavior. Raise β for faster adaptation, raise α for
  stability.
- `DIVERSITY_LAMBDA` — 0 = pure relevance (feed converges hard),
  0.3 default, 0.5+ = exploratory feed.
- Vector search uses an HNSW index (cosine). Unlike ivfflat, its recall
  doesn't depend on dataset size relative to a fixed `lists` parameter and it
  needs no rebuild after ingesting — nothing to tune at MVP scale.

## Tagging

Outfit tags originally came from the Unsplash *search query*, not the photo,
so an image found by "streetwear outfit" was tagged streetwear even when it
was plainly minimal. Audited against CLIP, only **42%** of stored tags matched
what the image actually showed — which corrupted the tag-affinity boost, the
"Recommended because…" explanations, the feed's theme filters, and the eval
harness's own ground truth.

`scripts/retag.py` reassigns tags by zero-shot scoring each outfit against the
aesthetic vocabulary:

```bash
python -m scripts.retag --dry-run     # preview
python -m scripts.retag               # apply
```

Two things make it work:

- **Multi-label, not argmax.** An outfit genuinely can be both monochrome and
  tailored; replacing one guess with another would lose that.
- **z-scored within each outfit.** Raw cosine sits in a narrow band
  (0.05–0.48) that's useless as a global threshold — what matters is which
  aesthetics stand out *for this image*.

Thresholds matter more than expected. At `--assign-z 1.0` tags are faithful
but so broad ("minimal" covering 30% of the catalog) that they stop
discriminating between users — lift over random fell from 5.1x to 3.1x. At the
default `--assign-z 1.5 --max-tags 2` coverage stays under 20% and lift rises
to **5.8x**. Re-runs score against the original CSV tags rather than the
previous run's output, so experiments don't compound.

Because tags became trustworthy, `TAG_AFFINITY_BOOST` was retuned 0.05 → 0.15
(the effect saturates there; raising it further changes nothing).

## Tests & migrations

```bash
pip install -r requirements-dev.txt

pytest                      # unit tests (no DB / CLIP needed)

# Offline recommender evaluation (needs the DB + ingested outfits).
# Run before and after any recommender change and compare the table:
python -m scripts.eval

# Schema is managed by Alembic. init_db() (called on API startup and by
# scripts) auto-upgrades to head; pre-Alembic databases are adopted by
# stamping the baseline revision. Manual usage:
alembic upgrade head
alembic revision -m "add column x"   # new migration
```

## Project layout

```
app/
  main.py          # FastAPI routes
  recommender.py   # blend formula, retrieval, MMR, explanations
  embeddings.py    # OpenCLIP wrapper (lazy singleton)
  models.py        # users / outfits / interactions (pgvector columns)
  schemas.py       # request/response models
  config.py, db.py
alembic/           # migrations (0001 = baseline schema)
scripts/
  ingest.py        # CSV → embedded outfit rows
  smoke_test.py    # end-to-end loop test
tests/             # pytest suite for recommender logic & schemas
```

## Next steps (Phase 2 hooks already in place)

- Session-based recommendations: add a session decay weight in
  `_weighted_mean` (recent interactions count more).
- Swap pgvector → FAISS/Pinecone behind `retrieve_candidates` only.
