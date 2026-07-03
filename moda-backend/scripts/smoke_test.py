"""End-to-end smoke test for the MODA recommendation loop.

Run AFTER ingesting outfits and starting the API:
    python -m scripts.smoke_test --base http://localhost:8000

It will:
  1. create a throwaway user
  2. submit a style quiz
  3. fetch recommendations
  4. like the top item, dislike the last item
  5. fetch recommendations again and show how the feed shifted
"""

from __future__ import annotations

import argparse
import random
import string

import requests


def rand_suffix(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    suffix = rand_suffix()
    user = requests.post(
        f"{base}/users",
        json={"email": f"smoke_{suffix}@moda.test", "username": f"smoke_{suffix}"},
        timeout=30,
    ).json()
    print(f"Created user {user['username']} ({user['id']})")

    quiz = {
        "user_id": user["id"],
        "aesthetics": ["minimal", "streetwear", "monochrome"],
        "colors": ["black", "white", "grey"],
        "fits": ["oversized", "tailored"],
        "occasions": ["everyday", "nightlife"],
        "brands": [],
        "inspirations": [],
    }
    result = requests.post(f"{base}/quiz", json=quiz, timeout=120).json()
    print(f"\nProfile: {result['profile_text']}")

    feed = requests.get(
        f"{base}/recommendations", params={"user_id": user["id"], "k": 10}, timeout=60
    ).json()
    items = feed["items"]
    if not items:
        print("\nNo outfits in DB yet — run scripts.ingest first.")
        return

    print(f"\nTop {len(items)} recommendations:")
    for it in items:
        o = it["outfit"]
        print(f"  {it['score']:.3f}  {o['image_url'][:60]}  | {it['explanation']}")

    liked, disliked = items[0]["outfit"]["id"], items[-1]["outfit"]["id"]
    for outfit_id, action in [(liked, "like"), (disliked, "dislike")]:
        requests.post(
            f"{base}/feedback",
            json={"user_id": user["id"], "outfit_id": outfit_id, "interaction_type": action},
            timeout=30,
        )
    print(f"\nLiked top item, disliked last item. Re-fetching feed...")

    feed2 = requests.get(
        f"{base}/recommendations", params={"user_id": user["id"], "k": 10}, timeout=60
    ).json()
    print(f"\nUpdated recommendations:")
    for it in feed2["items"]:
        o = it["outfit"]
        print(f"  {it['score']:.3f}  {o['image_url'][:60]}  | {it['explanation']}")


if __name__ == "__main__":
    main()
