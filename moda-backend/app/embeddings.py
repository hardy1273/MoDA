"""Embedding service built on OpenCLIP.

Images and text are projected into the same vector space, which is what lets
us compare a *text* taste profile against *image* outfit embeddings with
plain cosine similarity.

torch/open_clip are imported lazily so the API boots fast and code paths that
never embed (health checks, saved-outfit reads) never pay the load cost.
"""

from __future__ import annotations

import threading

import numpy as np
from PIL import Image

from app.config import get_settings

_lock = threading.Lock()
_model = None
_preprocess = None
_tokenizer = None
_torch = None


def _load():
    global _model, _preprocess, _tokenizer, _torch
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        import open_clip
        import torch

        settings = get_settings()
        # "hf-hub:org/repo" names (e.g. Marqo/marqo-fashionCLIP) carry their
        # own weights — open_clip rejects a pretrained tag alongside them.
        if settings.clip_model.startswith("hf-hub:"):
            model, _, preprocess = open_clip.create_model_and_transforms(settings.clip_model)
        else:
            model, _, preprocess = open_clip.create_model_and_transforms(
                settings.clip_model, pretrained=settings.clip_pretrained
            )
        model.eval()
        _torch = torch
        _model = model
        _preprocess = preprocess
        _tokenizer = open_clip.get_tokenizer(settings.clip_model)


def _normalize(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    norm = np.where(norm == 0, 1.0, norm)
    return v / norm


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a batch of short phrases. Returns (n, dim) L2-normalized."""
    _load()
    with _torch.no_grad():
        tokens = _tokenizer(texts)
        feats = _model.encode_text(tokens)
    return _normalize(feats.cpu().numpy().astype(np.float32))


def embed_image(image: Image.Image) -> np.ndarray:
    """Embed a single PIL image. Returns (dim,) L2-normalized."""
    _load()
    with _torch.no_grad():
        tensor = _preprocess(image.convert("RGB")).unsqueeze(0)
        feats = _model.encode_image(tensor)
    return _normalize(feats.cpu().numpy().astype(np.float32))[0]


def embed_profile_phrases(phrases: list[str], weights: list[float] | None = None) -> np.ndarray:
    """Embed several short taste phrases and (weighted-)average them.

    CLIP's text encoder is trained on short captions (77-token limit), so
    averaging multiple compact phrases is more faithful than embedding one
    long paragraph. Weights let high-signal phrases (aesthetics) count more
    than generic ones (colors, occasions).
    """
    if not phrases:
        raise ValueError("No phrases to embed")
    vecs = embed_texts(phrases)
    if weights is not None:
        if len(weights) != len(phrases):
            raise ValueError("weights must match phrases")
        w = np.asarray(weights, dtype=np.float32)[:, None]
        return _normalize((vecs * w).sum(axis=0) / w.sum())
    return _normalize(vecs.mean(axis=0))
