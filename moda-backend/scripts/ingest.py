"""Ingest curated outfit images into the MODA database.

Usage:
    python -m scripts.ingest --csv data/outfits.csv [--blend-caption]

CSV format (header required):
    image,caption,style_tags,color_tags,occasion_tags

    - image: local file path OR http(s) URL
    - caption: short descriptive caption (CLIP-friendly, < ~60 words)
    - *_tags: pipe-separated, e.g.  streetwear|oversized|minimal

Example row:
    images/fit_001.jpg,"Neutral oversized minimal streetwear outfit with black
    trousers and layered hoodie",streetwear|minimal|oversized,black|neutral,everyday

Flags:
    --blend-caption   average the image embedding with the caption's text
                      embedding (70/30). Helps when images are noisy
                      (busy backgrounds, multiple people).
    --update          re-embed and update rows whose image_url already exists
                      instead of skipping them.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from sqlalchemy import select

from app import models
from app.db import SessionLocal, init_db
from app.embeddings import embed_image, embed_texts


def load_image(source: str) -> Image.Image:
    if source.startswith(("http://", "https://")):
        resp = requests.get(source, timeout=20)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content))
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(source)
    return Image.open(path)


def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip().lower() for t in raw.split("|") if t.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest outfit images into MODA")
    parser.add_argument("--csv", required=True, help="Path to outfits CSV")
    parser.add_argument("--blend-caption", action="store_true")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    inserted = updated = skipped = failed = 0
    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Ingesting {len(rows)} outfits...")
    for i, row in enumerate(rows, 1):
        source = (row.get("image") or "").strip()
        if not source:
            print(f"[{i}] missing image column, skipping")
            failed += 1
            continue

        existing = db.scalar(select(models.Outfit).where(models.Outfit.image_url == source))
        if existing and not args.update:
            skipped += 1
            continue

        try:
            img = load_image(source)
            vec = embed_image(img)

            caption = (row.get("caption") or "").strip() or None
            if args.blend_caption and caption:
                text_vec = embed_texts([caption])[0]
                vec = 0.7 * vec + 0.3 * text_vec
                vec = vec / np.linalg.norm(vec)

            if existing:
                outfit = existing
                updated += 1
            else:
                outfit = models.Outfit(image_url=source)
                inserted += 1

            outfit.caption = caption
            outfit.style_tags = parse_tags(row.get("style_tags"))
            outfit.color_tags = parse_tags(row.get("color_tags"))
            outfit.occasion_tags = parse_tags(row.get("occasion_tags"))
            outfit.embedding = vec.tolist()
            db.add(outfit)

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
