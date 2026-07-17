"""Offline evaluation harness for the recommender.

Ground truth is derived from tags: for each aesthetic profile we hold out
a set of outfits carrying that tag, seed the user with the quiz plus a few
likes of *other* same-tag outfits, and measure whether the recommender
surfaces the held-out ones.

Metrics (averaged over profiles x seeds):
  on-aes@10        share of the top 10 carrying the profile's tag
  holdout-R@50     fraction of the held-out tagged outfits in the top 50
  overlap@10       mean pairwise overlap of different profiles' top 10
                   (lower = more personalized)

Usage:
    python -m scripts.eval [--seeds 3] [--holdout 20] [--likes 5] [--json out.json]

Run before and after any recommender change; compare the table.
"""

from __future__ import annotations

import argparse
import json
import random
import string
import uuid
from itertools import combinations

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app import models
from app.db import SessionLocal
from app.main import app

PROFILES: dict[str, dict] = {
    "streetwear": {"aesthetics": ["streetwear"], "colors": ["black"], "fits": ["oversized"], "occasions": ["everyday"]},
    "old money": {"aesthetics": ["old money"], "colors": ["beige"], "fits": ["tailored"], "occasions": ["formal"]},
    "vintage": {"aesthetics": ["vintage"], "colors": ["brown"], "fits": ["relaxed"], "occasions": ["casual"]},
    "minimal": {"aesthetics": ["minimal"], "colors": ["monochrome"], "fits": ["slim"], "occasions": ["everyday"]},
    "techwear": {"aesthetics": ["techwear"], "colors": ["black"], "fits": ["relaxed"], "occasions": ["everyday"]},
}


def tagged_outfits(db, tag: str) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(models.Outfit.id).where(models.Outfit.style_tags.contains([tag]))
        ).all()
    )


def run_profile(
    client: TestClient, db, name: str, quiz: dict, rng: random.Random,
    holdout_n: int, likes_n: int,
) -> tuple[dict, list[uuid.UUID], uuid.UUID] | None:
    tag = quiz["aesthetics"][0]
    pool = tagged_outfits(db, tag)
    if len(pool) < holdout_n + likes_n:
        print(f"  [skip] {name!r}: only {len(pool)} outfits tagged {tag!r}")
        return None
    rng.shuffle(pool)
    holdout = set(pool[:holdout_n])
    seeds = pool[holdout_n : holdout_n + likes_n]

    s = "eval_" + "".join(rng.choices(string.ascii_lowercase, k=10))
    r = client.post(
        "/auth/signup",
        json={"email": f"{s}@example.com", "username": s, "password": "evalharness1"},
    )
    user_id = uuid.UUID(r.json()["user"]["id"])
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/quiz", json={**quiz, "brands": [], "inspirations": []}, headers=h)
    for oid in seeds:
        client.post("/feedback", json={"outfit_id": str(oid), "interaction_type": "like"}, headers=h)

    items = client.get("/recommendations?k=50", headers=h).json()["items"]
    top_ids = [uuid.UUID(i["outfit"]["id"]) for i in items]
    top10_tags = [i["outfit"]["style_tags"] for i in items[:10]]

    metrics = {
        "on_aes_10": sum(tag in tags for tags in top10_tags) / 10,
        "holdout_r_50": len(set(top_ids[:50]) & holdout) / len(holdout),
    }
    return metrics, top_ids[:10], user_id


def cleanup(db, user_ids: list[uuid.UUID]) -> None:
    if not user_ids:
        return
    db.execute(delete(models.Interaction).where(models.Interaction.user_id.in_(user_ids)))
    db.execute(delete(models.User).where(models.User.id.in_(user_ids)))
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the recommender offline")
    parser.add_argument("--seeds", type=int, default=3, help="random seeds per profile")
    parser.add_argument("--holdout", type=int, default=20)
    parser.add_argument("--likes", type=int, default=5)
    parser.add_argument("--json", help="write results to this JSON file")
    args = parser.parse_args()

    db = SessionLocal()
    per_profile: dict[str, dict[str, list[float]]] = {}
    eval_users: list[uuid.UUID] = []

    with TestClient(app) as client:
        for seed in range(args.seeds):
            top10s: dict[str, list[uuid.UUID]] = {}
            for name, quiz in PROFILES.items():
                rng = random.Random(1000 * seed + hash(name) % 1000)
                out = run_profile(client, db, name, quiz, rng, args.holdout, args.likes)
                if out is None:
                    continue
                metrics, top10, user_id = out
                eval_users.append(user_id)
                top10s[name] = top10
                bucket = per_profile.setdefault(name, {"on_aes_10": [], "holdout_r_50": []})
                for k, v in metrics.items():
                    bucket[k].append(v)
            # cross-profile overlap for this seed
            overlaps = [
                len(set(top10s[a]) & set(top10s[b])) / 10
                for a, b in combinations(top10s, 2)
            ]
            if overlaps:
                per_profile.setdefault("_overlap", {"overlap_10": []})["overlap_10"].append(
                    sum(overlaps) / len(overlaps)
                )

    cleanup(db, eval_users)
    db.close()

    print(f"\n{'profile':<14}{'on-aes@10':>12}{'holdout-R@50':>15}")
    means = {"on_aes_10": [], "holdout_r_50": []}
    for name in PROFILES:
        if name not in per_profile:
            continue
        m = per_profile[name]
        oa = sum(m["on_aes_10"]) / len(m["on_aes_10"])
        hr = sum(m["holdout_r_50"]) / len(m["holdout_r_50"])
        means["on_aes_10"].append(oa)
        means["holdout_r_50"].append(hr)
        print(f"{name:<14}{oa:>12.3f}{hr:>15.3f}")
    if means["on_aes_10"]:
        print("-" * 41)
        print(
            f"{'MEAN':<14}{sum(means['on_aes_10']) / len(means['on_aes_10']):>12.3f}"
            f"{sum(means['holdout_r_50']) / len(means['holdout_r_50']):>15.3f}"
        )
    ov = per_profile.get("_overlap", {}).get("overlap_10", [])
    if ov:
        print(f"\ncross-profile overlap@10: {sum(ov) / len(ov):.3f} (lower is better)")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(per_profile, f, indent=2, default=str)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
