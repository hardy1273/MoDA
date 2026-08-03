"""Re-tag outfits from what the images actually look like.

The seeded tags came from the Unsplash *search query*, not the photo, so an
image found by "streetwear outfit" is tagged streetwear even when it's
plainly minimal. Audited against CLIP, only ~42% of stored tags matched the
image.

This assigns tags by zero-shot scoring each outfit against the aesthetic
vocabulary. Two details matter:

  * Multi-label, not argmax. An outfit really can be both monochrome and
    tailored; replacing one guess with another guess would lose that.
  * Scores are z-scored *within each outfit*. Raw cosine sits in a narrow
    band (0.05–0.48) that's useless as a global threshold — what matters is
    which aesthetics stand out for this particular image.

The original query tag is kept only when CLIP at least partly agrees
(KEEP_Z), which prunes clear mislabels without discarding genuine
multi-label cases.

Usage:
    python -m scripts.retag --dry-run     # preview, change nothing
    python -m scripts.retag               # apply
"""

from __future__ import annotations

import argparse
from collections import Counter

import numpy as np
from sqlalchemy import select

from app import models
from app.db import SessionLocal
from app.embeddings import embed_texts

AESTHETICS = [
    "minimal", "modern", "old money", "chic", "tailored", "vintage",
    "streetwear", "layered", "relaxed", "monochrome", "preppy",
    "oversized", "retro", "techwear", "utility",
]

# Defaults, overridable from the CLI. Tuned empirically: looser settings make
# tags faithful to each image but so broad ("minimal" covering 30% of the
# catalog) that they stop discriminating between users. See --help.
ASSIGN_Z = 1.5
KEEP_Z = 1.0
MAX_TAGS = 2

# Is this even a wearable outfit? Scored against distractors so crowd shots,
# fabric close-ups and scenery can be flagged rather than recommended.
SUBJECT = "a person wearing a full outfit"
DISTRACTORS = [
    "a close-up of fabric texture",
    "a crowd of people at an event",
    "an empty landscape or building",
    "a product on a plain background",
]


def tags_for(
    z: np.ndarray,
    original: list[str],
    assign_z: float = ASSIGN_Z,
    keep_z: float = KEEP_Z,
    max_tags: int = MAX_TAGS,
) -> list[str]:
    """Pick this outfit's tags from its per-aesthetic z-scores."""
    chosen = {AESTHETICS[i] for i in np.where(z > assign_z)[0]}
    for tag in original:
        idx = AESTHETICS.index(tag) if tag in AESTHETICS else -1
        if idx >= 0 and z[idx] > keep_z:
            chosen.add(tag)
    if not chosen:  # never leave an outfit untagged
        chosen = {AESTHETICS[int(np.argmax(z))]}
    # Strongest first, capped
    return sorted(chosen, key=lambda t: -z[AESTHETICS.index(t)])[:max_tags]


def original_tags_from_csv(path: str) -> dict[str, list[str]]:
    """Query-derived tags as originally fetched, keyed by image URL.

    Lets experiments restart from the same baseline instead of compounding
    one run's output into the next.
    """
    import csv

    with open(path, newline="", encoding="utf-8") as f:
        return {
            row["image"]: [t.strip().lower() for t in row["style_tags"].split("|") if t.strip()]
            for row in csv.DictReader(f)
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-tag outfits from image content")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="0 = all outfits")
    parser.add_argument("--assign-z", type=float, default=ASSIGN_Z,
                        help="z-score to assign an aesthetic (higher = fewer, sharper tags)")
    parser.add_argument("--keep-z", type=float, default=KEEP_Z,
                        help="z-score to keep the original query-derived tag")
    parser.add_argument("--max-tags", type=int, default=MAX_TAGS)
    parser.add_argument("--baseline-csv", default="data/outfits.csv",
                        help="score against the ORIGINAL query tags, so repeated "
                             "runs don't compound; '' uses whatever is in the DB")
    args = parser.parse_args()

    baseline = original_tags_from_csv(args.baseline_csv) if args.baseline_csv else {}

    labels = embed_texts([f"{a} style outfit" for a in AESTHETICS])
    quality = embed_texts([SUBJECT] + DISTRACTORS)

    db = SessionLocal()
    stmt = select(models.Outfit)
    if args.limit:
        stmt = stmt.limit(args.limit)
    outfits = db.scalars(stmt).all()
    print(f"Scoring {len(outfits)} outfits...\n")

    changed = unchanged = flagged = 0
    tag_counts: Counter[str] = Counter()
    examples: list[str] = []

    for outfit in outfits:
        v = np.asarray(outfit.embedding, dtype=np.float32)

        sims = labels @ v
        z = (sims - sims.mean()) / (sims.std() or 1.0)
        prior = baseline.get(outfit.image_url, [t.lower() for t in (outfit.style_tags or [])])
        new_tags = tags_for(z, prior, args.assign_z, args.keep_z, args.max_tags)

        # Subject check: does it look more like an outfit than a distractor?
        q = quality @ v
        is_outfit = bool(np.argmax(q) == 0)
        if not is_outfit:
            flagged += 1

        old = sorted(prior)
        if old != sorted(new_tags):
            changed += 1
            if len(examples) < 8:
                examples.append(f"  {str(old):<32} -> {new_tags}")
        else:
            unchanged += 1
        tag_counts.update(new_tags)

        if not args.dry_run:
            outfit.style_tags = new_tags
            db.add(outfit)

    if not args.dry_run:
        db.commit()
    db.close()

    print("sample changes:")
    print("\n".join(examples))
    print(f"\nchanged={changed}  unchanged={unchanged}")
    print(f"images that don't look like a worn outfit: {flagged} "
          f"({flagged/len(outfits):.0%}) — left in place, not deleted")
    print("\nnew tag distribution:")
    for tag, n in tag_counts.most_common():
        print(f"  {tag:<12} {n}")
    if args.dry_run:
        print("\n(dry run — nothing written)")


if __name__ == "__main__":
    main()
