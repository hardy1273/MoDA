"""Populate outfit_items: shop-the-look links via CLIP similarity.

For each outfit, retrieve the nearest items in embedding space, then pick
greedily with one item per category (an outfit needs a hoodie AND pants,
not five hoodies), up to --max-items pieces above --min-score.

Usage:
    python -m scripts.link_items [--max-items 5] [--min-score 0.45]

Idempotent: re-running replaces each outfit's links.
"""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import delete, select

from app import models
from app.db import SessionLocal, init_db


def pick_shop_the_look(
    candidates: list[tuple[uuid.UUID, str, float]], max_items: int, min_score: float
) -> list[tuple[uuid.UUID, float]]:
    """Greedy pick: highest-scoring item per distinct category.

    candidates: (item_id, category, score) sorted by score descending.
    Returns up to max_items (item_id, score) pairs.
    """
    picked: list[tuple[uuid.UUID, float]] = []
    seen_categories: set[str] = set()
    for item_id, category, score in candidates:
        if len(picked) >= max_items:
            break
        if score < min_score or category in seen_categories:
            continue
        picked.append((item_id, score))
        seen_categories.add(category)
    return picked


def main() -> None:
    parser = argparse.ArgumentParser(description="Link outfits to similar items")
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=0.45)
    parser.add_argument("--pool", type=int, default=40, help="nearest items considered per outfit")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    outfit_ids = db.scalars(select(models.Outfit.id)).all()
    print(f"Linking {len(outfit_ids)} outfits...")
    linked = empty = 0
    for i, outfit_id in enumerate(outfit_ids, 1):
        outfit = db.get(models.Outfit, outfit_id)
        dist = models.Item.embedding.cosine_distance(list(outfit.embedding))
        rows = db.execute(
            select(models.Item.id, models.Item.category, (1 - dist).label("score"))
            .where(models.Item.status == models.ITEM_APPROVED)
            .order_by(dist)
            .limit(args.pool)
        ).all()
        picks = pick_shop_the_look(
            [(r.id, r.category, float(r.score)) for r in rows], args.max_items, args.min_score
        )

        db.execute(delete(models.OutfitItem).where(models.OutfitItem.outfit_id == outfit_id))
        for rank, (item_id, score) in enumerate(picks):
            db.add(
                models.OutfitItem(outfit_id=outfit_id, item_id=item_id, rank=rank, score=score)
            )
        linked += 1 if picks else 0
        empty += 0 if picks else 1

        if i % 100 == 0:
            db.commit()
            print(f"  ...{i}/{len(outfit_ids)}")

    db.commit()
    db.close()
    print(f"Done. outfits with links={linked}, without={empty}")


if __name__ == "__main__":
    main()
