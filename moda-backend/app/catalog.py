"""Shared catalog helpers: image loading and listing embeddings.

Used by both the seller-listing endpoints and the ingest scripts so a
seller-created item lands in exactly the same vector space as the seeded
catalog.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import requests
from PIL import Image

from app.embeddings import embed_image, embed_texts

# Image bytes we're willing to pull from a remote URL
MAX_IMAGE_BYTES = 15 * 1024 * 1024


def load_image(source: str) -> Image.Image:
    """Load a PIL image from an http(s) URL or a local path."""
    if source.startswith(("http://", "https://")):
        resp = requests.get(source, timeout=20)
        resp.raise_for_status()
        if len(resp.content) > MAX_IMAGE_BYTES:
            raise ValueError("Image is too large")
        return Image.open(io.BytesIO(resp.content))
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(source)
    return Image.open(path)


def validate_listing_image_url(url: str) -> str:
    """Reject anything we shouldn't fetch server-side.

    NOTE: this is scheme-level validation only. A production deployment
    should upload to object storage from the browser (or fetch through an
    egress proxy) rather than having the API fetch seller-supplied URLs,
    which is an SSRF vector against internal network addresses.
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Image URL must start with http:// or https://")
    return url


def embed_listing(image: Image.Image, name: str, caption: str | None) -> list[float]:
    """Blend the image embedding 70/30 with its name+caption text.

    The text share bakes category words ("hoodie", "sneakers") into the
    vector, which matters for shop-the-look category matching.
    """
    vec = embed_image(image)
    text = f"{name}. {caption}" if caption else name
    text_vec = embed_texts([text])[0]
    vec = 0.7 * vec + 0.3 * text_vec
    return (vec / np.linalg.norm(vec)).tolist()
