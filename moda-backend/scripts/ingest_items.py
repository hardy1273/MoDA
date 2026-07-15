"""Ingest item photos into the items table.

Usage:
    python -m scripts.ingest_items --csv data/items.csv [--update]

Embeds each image with CLIP, blended 70/30 with the item's name + caption
text so category words ("hoodie", "sneakers") are baked into the vector.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
from sqlalchemy import select

from app import models
from app.db import SessionLocal, init_db
from app.embeddings import embed_image, embed_texts
from scripts.ingest import load_image, parse_tags


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest item images into MODA")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    import csv

    init_db()
    db = SessionLocal()

    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    inserted = updated = skipped = failed = 0
    print(f"Ingesting {len(rows)} items...")
    for i, row in enumerate(rows, 1):
        source = (row.get("image") or "").strip()
        if not source:
            failed += 1
            continue

        existing = db.scalar(select(models.Item).where(models.Item.image_url == source))
        if existing and not args.update:
            skipped += 1
            continue

        try:
            vec = embed_image(load_image(source))
            name = (row.get("name") or "").strip() or row.get("category", "piece")
            caption = (row.get("caption") or "").strip() or None
            text = f"{name}. {caption}" if caption else name
            text_vec = embed_texts([text])[0]
            vec = 0.7 * vec + 0.3 * text_vec
            vec = vec / np.linalg.norm(vec)

            if existing:
                item = existing
                updated += 1
            else:
                item = models.Item(image_url=source)
                inserted += 1

            item.name = name
            item.category = (row.get("category") or "").strip().lower()
            item.caption = caption
            item.style_tags = parse_tags(row.get("style_tags"))
            item.color_tags = parse_tags(row.get("color_tags"))
            item.price_cents = int(row.get("price_cents") or 0)
            item.embedding = vec.tolist()
            db.add(item)

            if i % 25 == 0:
                db.commit()
                print(f"  ...{i}/{len(rows)}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[{i}] FAILED {source}: {e}", file=sys.stderr)

    db.commit()
    db.close()
    print(f"Done. inserted={inserted} updated={updated} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
