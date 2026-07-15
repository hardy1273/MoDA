"""Fetch item-focused photos (individual pieces) from the Unsplash API.

Like fetch_dataset.py but for single garments: one query per category,
producing data/items.csv ready for scripts/ingest_items.py. Prices are
deterministic placeholders within a realistic per-category range (stable
across re-runs; replaced by real seller pricing later).

Usage:
    python -m scripts.fetch_items [--out data/items.csv] [--pages 2]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from scripts.fetch_dataset import hex_to_color_tag, search_page

# (search query, category, min $, max $)
CATEGORIES: list[tuple[str, str, int, int]] = [
    ("hoodie sweatshirt clothing", "hoodie", 40, 120),
    ("t-shirt clothing minimal", "t-shirt", 20, 60),
    ("button up shirt clothing", "shirt", 35, 90),
    ("denim jacket clothing", "jacket", 60, 180),
    ("wool overcoat fashion", "coat", 90, 300),
    ("knit sweater clothing", "sweater", 45, 140),
    ("jeans denim pants", "jeans", 50, 140),
    ("tailored trousers pants", "trousers", 45, 130),
    ("skirt fashion clothing", "skirt", 30, 90),
    ("dress fashion minimal", "dress", 40, 160),
    ("sneakers shoes", "sneakers", 60, 200),
    ("leather boots shoes", "boots", 80, 250),
    ("leather handbag", "bag", 40, 220),
]


def placeholder_price_cents(photo_id: str, lo: int, hi: int) -> int:
    """Deterministic pseudo-price in [lo, hi] dollars, ending in .99 or .49.

    Hash-derived so the same photo always gets the same price, but spread
    uniformly across the category's range.
    """
    h = int(hashlib.sha256(photo_id.encode()).hexdigest()[:8], 16)
    dollars = lo + h % max(hi - lo, 1)
    cents = 99 if h % 2 == 0 else 49
    return dollars * 100 + cents


def item_name(photo: dict, category: str) -> str:
    colors = hex_to_color_tag(photo.get("color"))
    base = f"{colors[0]} {category}" if colors else category
    return base[0].upper() + base[1:]


def item_row(photo: dict, category: str, lo: int, hi: int) -> dict:
    caption = (photo.get("alt_description") or photo.get("description") or "").strip() or None
    user = photo.get("user") or {}
    return {
        "image": photo["urls"]["regular"],
        "name": item_name(photo, category),
        "category": category,
        "caption": (caption or "")[:200],
        "color_tags": "|".join(hex_to_color_tag(photo.get("color"))),
        "price_cents": placeholder_price_cents(photo["id"], lo, hi),
        "credit": f"{user.get('name', 'Unknown')} on Unsplash ({photo.get('links', {}).get('html', '')})",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch item photos from Unsplash")
    parser.add_argument("--out", default="data/items.csv")
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--per-page", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()

    load_dotenv()
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        sys.exit("UNSPLASH_ACCESS_KEY is not set (see moda-backend/.env).")

    rows: dict[str, dict] = {}
    n = 0
    rate_limited = False
    for query, category, lo, hi in CATEGORIES:
        if rate_limited:
            break
        for page in range(1, args.pages + 1):
            try:
                data = search_page(key, query, page, args.per_page)
            except RuntimeError as e:
                print(f"\nStopping early: {e}", file=sys.stderr)
                rate_limited = True
                break
            n += 1
            new = 0
            for photo in data.get("results", []):
                pid = photo.get("id")
                if not pid or pid in rows:
                    continue
                rows[pid] = item_row(photo, category, lo, hi)
                new += 1
            print(f"[{n:>2}] {category!r} p{page}: +{new} (total {len(rows)})")
            if page >= data.get("total_pages", 0):
                break
            time.sleep(args.sleep)

    if not rows:
        sys.exit("No items fetched — check your access key.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["image", "name", "category", "caption", "color_tags", "price_cents", "credit"]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows.values())

    print(f"\nWrote {len(rows)} items to {out}")
    print(f"Next: python -m scripts.ingest_items --csv {out}")


if __name__ == "__main__":
    main()
