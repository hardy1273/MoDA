"""Build a licensed outfit dataset from the Unsplash API.

Searches fashion queries across the quiz's aesthetic axes, dedupes results,
and writes an ingest-ready CSV (hotlinked image URLs, per Unsplash
guidelines — no local downloads needed).

Usage:
    export UNSPLASH_ACCESS_KEY=...   # free at https://unsplash.com/developers
    python -m scripts.fetch_dataset [--out data/outfits.csv] [--pages 2]
    python -m scripts.ingest --csv data/outfits.csv --blend-caption

Free demo tier is 50 requests/hour; the default settings (~2 pages x 16
queries = 32 requests) stay under that and yield 600+ unique photos.
The CSV has an extra `credit` column (photographer attribution) that
scripts/ingest.py ignores.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

API_SEARCH = "https://api.unsplash.com/search/photos"

# (search query, style_tags, occasion_tags) — one axis per quiz aesthetic,
# plus fit/occasion flavored queries so those quiz answers retrieve well too.
QUERIES: list[tuple[str, list[str], list[str]]] = [
    ("minimal outfit street style", ["minimal"], ["everyday"]),
    ("minimalist fashion monochrome", ["minimal", "monochrome"], ["everyday"]),
    ("streetwear outfit", ["streetwear"], ["everyday"]),
    ("oversized streetwear fashion", ["streetwear", "oversized"], ["everyday"]),
    ("vintage outfit fashion", ["vintage"], ["casual"]),
    ("retro fashion street style", ["vintage", "retro"], ["casual"]),
    ("modern fashion editorial", ["modern"], ["everyday"]),
    ("contemporary chic outfit", ["modern", "chic"], ["work"]),
    ("old money style outfit", ["old money", "tailored"], ["formal"]),
    ("preppy classic menswear", ["old money", "preppy"], ["work"]),
    ("techwear outfit", ["techwear"], ["everyday"]),
    ("utility fashion functional clothing", ["techwear", "utility"], ["everyday"]),
    ("tailored suit street style", ["tailored"], ["formal"]),
    ("relaxed casual outfit linen", ["relaxed"], ["travel"]),
    ("layered autumn outfit fashion", ["layered"], ["everyday"]),
    ("evening night out outfit", ["chic"], ["nightlife"]),
]

# Coarse named colors for mapping Unsplash's dominant-color hex → color tag.
NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "black": (20, 20, 20),
    "white": (245, 245, 245),
    "grey": (128, 128, 128),
    "beige": (207, 185, 151),
    "brown": (110, 74, 46),
    "navy": (32, 42, 68),
    "blue": (70, 110, 180),
    "green": (80, 120, 80),
    "red": (170, 50, 50),
    "pink": (220, 150, 170),
    "yellow": (210, 190, 90),
    "orange": (215, 130, 60),
    "purple": (120, 80, 160),
    "cream": (240, 230, 210),
}


def hex_to_color_tag(hex_color: str | None) -> list[str]:
    if not hex_color or not hex_color.startswith("#") or len(hex_color) != 7:
        return []
    try:
        r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        return []
    name = min(
        NAMED_COLORS,
        key=lambda n: sum((a - b) ** 2 for a, b in zip(NAMED_COLORS[n], (r, g, b))),
    )
    return [name]


def search_page(key: str, query: str, page: int, per_page: int) -> dict:
    resp = requests.get(
        API_SEARCH,
        params={
            "query": query,
            "page": page,
            "per_page": per_page,
            "orientation": "portrait",
            "content_filter": "high",
        },
        headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"},
        timeout=20,
    )
    if resp.status_code == 403:
        raise RuntimeError("Unsplash rate limit hit (50 req/hour on the demo tier)")
    resp.raise_for_status()
    return resp.json()


def photo_row(photo: dict, style: list[str], occasion: list[str], query: str) -> dict:
    caption = (photo.get("alt_description") or photo.get("description") or query).strip()
    user = photo.get("user") or {}
    return {
        "image": photo["urls"]["regular"],
        "caption": caption[:200],
        "style_tags": "|".join(style),
        "color_tags": "|".join(hex_to_color_tag(photo.get("color"))),
        "occasion_tags": "|".join(occasion),
        "credit": f"{user.get('name', 'Unknown')} on Unsplash ({photo.get('links', {}).get('html', '')})",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch outfit dataset from Unsplash")
    parser.add_argument("--out", default="data/outfits.csv")
    parser.add_argument("--pages", type=int, default=2, help="pages per query (30 photos each)")
    parser.add_argument("--per-page", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds between requests")
    args = parser.parse_args()

    load_dotenv()
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        sys.exit(
            "UNSPLASH_ACCESS_KEY is not set.\n"
            "Create a free app at https://unsplash.com/developers and add\n"
            "UNSPLASH_ACCESS_KEY=... to moda-backend/.env"
        )

    rows: dict[str, dict] = {}  # photo id -> row (dedup across queries)
    requests_made = 0
    rate_limited = False
    for query, style, occasion in QUERIES:
        if rate_limited:
            break
        for page in range(1, args.pages + 1):
            try:
                data = search_page(key, query, page, args.per_page)
            except RuntimeError as e:
                print(f"\nStopping early: {e}", file=sys.stderr)
                rate_limited = True
                break
            requests_made += 1
            new = 0
            for photo in data.get("results", []):
                pid = photo.get("id")
                if not pid or pid in rows:
                    continue
                rows[pid] = photo_row(photo, style, occasion, query)
                new += 1
            print(f"[{requests_made:>2}] {query!r} p{page}: +{new} (total {len(rows)})")
            if page >= data.get("total_pages", 0):
                break  # this query has no more pages — move on to the next one
            time.sleep(args.sleep)

    if not rows:
        sys.exit("No photos fetched — check your access key.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["image", "caption", "style_tags", "color_tags", "occasion_tags", "credit"]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows.values())

    print(f"\nWrote {len(rows)} outfits to {out}")
    print(f"Next: python -m scripts.ingest --csv {out} --blend-caption")


if __name__ == "__main__":
    main()
