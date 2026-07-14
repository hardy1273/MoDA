"""Unit tests for the recommendation engine's pure logic.

No Postgres or CLIP required: db-dependent pieces are monkeypatched and
outfits are stand-in objects with just .id and .embedding.
"""

import uuid
from types import SimpleNamespace

import numpy as np
import pytest

from app import recommender
from app.config import get_settings
from app.schemas import QuizSubmission


def quiz(**kwargs) -> QuizSubmission:
    return QuizSubmission(**kwargs)


# ---------------------------------------------------------------------------
# Profile building
# ---------------------------------------------------------------------------

class TestBuildProfilePhrases:
    def test_full_quiz_maps_to_clip_phrases(self):
        phrases = recommender.build_profile_phrases(
            quiz(
                aesthetics=["minimal", "streetwear"],
                colors=["black", "white"],
                fits=["oversized"],
                occasions=["everyday"],
                brands=["acne"],
                inspirations=["rick owens"],
            )
        )
        assert "minimal style outfit" in phrases
        assert "streetwear style outfit" in phrases
        assert "outfit in black, white colors" in phrases
        assert "oversized fit clothing" in phrases
        assert "outfit for everyday" in phrases
        assert "acne style clothing" in phrases
        assert "fashion inspired by rick owens" in phrases

    def test_empty_quiz_falls_back_to_default_phrase(self):
        assert recommender.build_profile_phrases(quiz()) == [
            "modern minimal everyday outfit"
        ]

    def test_brands_and_inspirations_capped_at_five(self):
        many = [f"brand{i}" for i in range(10)]
        phrases = recommender.build_profile_phrases(quiz(brands=many, inspirations=many))
        assert sum("style clothing" in p for p in phrases) == 5
        assert sum("fashion inspired by" in p for p in phrases) == 5


class TestBuildProfileText:
    def test_mentions_each_answered_section(self):
        text = recommender.build_profile_text(
            quiz(aesthetics=["minimal"], fits=["slim"], colors=["black"], occasions=["work"])
        )
        assert "minimal aesthetics" in text
        assert "slim silhouettes" in text
        assert "black palette" in text
        assert "worn for work" in text

    def test_empty_quiz_gets_default_text(self):
        assert "minimal everyday" in recommender.build_profile_text(quiz())


# ---------------------------------------------------------------------------
# Vector math
# ---------------------------------------------------------------------------

class TestDecayFactor:
    def _now(self):
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)

    def test_fresh_interaction_full_weight(self):
        now = self._now()
        assert recommender.decay_factor(now, now, half_life_days=14) == pytest.approx(1.0)

    def test_half_life_halves_weight(self):
        from datetime import timedelta

        now = self._now()
        old = now - timedelta(days=14)
        assert recommender.decay_factor(old, now, half_life_days=14) == pytest.approx(0.5)

    def test_two_half_lives_quarter_weight(self):
        from datetime import timedelta

        now = self._now()
        old = now - timedelta(days=28)
        assert recommender.decay_factor(old, now, half_life_days=14) == pytest.approx(0.25)

    def test_zero_half_life_disables_decay(self):
        from datetime import timedelta

        now = self._now()
        old = now - timedelta(days=365)
        assert recommender.decay_factor(old, now, half_life_days=0) == 1.0

    def test_future_timestamp_clamped(self):
        from datetime import timedelta

        now = self._now()
        future = now + timedelta(days=3)
        assert recommender.decay_factor(future, now, half_life_days=14) == pytest.approx(1.0)


class TestL2:
    def test_normalizes_to_unit_length(self):
        v = recommender._l2(np.array([3.0, 4.0], dtype=np.float32))
        assert np.linalg.norm(v) == pytest.approx(1.0)

    def test_zero_vector_returned_unchanged(self):
        v = recommender._l2(np.zeros(4, dtype=np.float32))
        assert np.allclose(v, 0.0)


class TestComputeUserEmbedding:
    """Blend formula: alpha*quiz + beta*pos - gamma*neg, L2-normalized."""

    def _user(self, quiz_vec=None):
        return SimpleNamespace(id=uuid.uuid4(), quiz_embedding=quiz_vec)

    def _patch_means(self, monkeypatch, pos=None, neg=None):
        def fake(db, user_id, weights):
            if weights is recommender.POSITIVE_WEIGHTS:
                return pos
            return neg

        monkeypatch.setattr(recommender, "_weighted_mean", fake)

    def test_no_quiz_and_no_positives_returns_none(self, monkeypatch):
        self._patch_means(monkeypatch, pos=None, neg=None)
        assert recommender.compute_user_embedding(None, self._user()) is None

    def test_quiz_only_returns_normalized_quiz_vector(self, monkeypatch):
        self._patch_means(monkeypatch)
        dim = get_settings().embedding_dim
        q = np.zeros(dim, dtype=np.float32)
        q[0] = 2.0
        vec = recommender.compute_user_embedding(None, self._user(quiz_vec=q.tolist()))
        assert vec[0] == pytest.approx(1.0)
        assert np.linalg.norm(vec) == pytest.approx(1.0)

    def test_blend_arithmetic(self, monkeypatch):
        s = get_settings()
        dim = s.embedding_dim
        q = np.zeros(dim, dtype=np.float32); q[0] = 1.0
        p = np.zeros(dim, dtype=np.float32); p[1] = 1.0
        n = np.zeros(dim, dtype=np.float32); n[2] = 1.0
        self._patch_means(monkeypatch, pos=p, neg=n)

        vec = recommender.compute_user_embedding(None, self._user(quiz_vec=q.tolist()))

        expected = np.zeros(dim, dtype=np.float32)
        expected[0] = s.alpha_quiz
        expected[1] = s.beta_liked
        expected[2] = -s.gamma_disliked
        expected /= np.linalg.norm(expected)
        assert np.allclose(vec, expected, atol=1e-6)
        assert np.linalg.norm(vec) == pytest.approx(1.0)

    def test_positives_without_quiz_still_produce_embedding(self, monkeypatch):
        dim = get_settings().embedding_dim
        p = np.zeros(dim, dtype=np.float32); p[3] = 1.0
        self._patch_means(monkeypatch, pos=p)
        vec = recommender.compute_user_embedding(None, self._user())
        assert vec is not None
        assert vec[3] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# MMR re-ranking
# ---------------------------------------------------------------------------

def _outfit(vec):
    return SimpleNamespace(id=uuid.uuid4(), embedding=list(vec))


class TestMmrRerank:
    def test_lambda_zero_keeps_relevance_order(self):
        cands = [(_outfit([1, 0]), 0.9), (_outfit([1, 0]), 0.8), (_outfit([0, 1]), 0.7)]
        assert recommender.mmr_rerank(cands, k=2, lam=0.0) == cands[:2]

    def test_short_candidate_list_returned_as_is(self):
        cands = [(_outfit([1, 0]), 0.9)]
        assert recommender.mmr_rerank(cands, k=5, lam=0.5) == cands

    def test_diversity_demotes_near_duplicate(self):
        # Two nearly identical top outfits + one distinct slightly-less-relevant one.
        a = (_outfit([1.0, 0.0]), 0.90)
        a_dup = (_outfit([0.999, 0.01]), 0.89)
        b = (_outfit([0.0, 1.0]), 0.80)

        picked = recommender.mmr_rerank([a, a_dup, b], k=2, lam=0.5)
        picked_ids = [o.id for o, _ in picked]
        assert picked_ids[0] == a[0].id
        # MMR should prefer the distinct outfit over the near-duplicate
        assert picked_ids[1] == b[0].id

    def test_returns_exactly_k_items(self):
        cands = [(_outfit(np.random.rand(4)), 1.0 - i * 0.01) for i in range(10)]
        assert len(recommender.mmr_rerank(cands, k=5, lam=0.3)) == 5


# ---------------------------------------------------------------------------
# Tag-affinity boost
# ---------------------------------------------------------------------------

class TestTagBoost:
    def _outfit(self, style=(), color=(), occasion=()):
        return SimpleNamespace(
            style_tags=list(style), color_tags=list(color), occasion_tags=list(occasion)
        )

    def test_no_matching_tags_no_boost(self):
        assert recommender.tag_boost(self._outfit(style=["vintage"]), {"minimal"}) == 0.0

    def test_one_matching_tag(self):
        boost = recommender.tag_boost(self._outfit(style=["minimal"]), {"minimal"})
        assert boost == pytest.approx(recommender.settings.tag_affinity_boost)

    def test_boost_capped_at_two_tags(self):
        o = self._outfit(style=["minimal", "modern"], color=["black"], occasion=["everyday"])
        taste = {"minimal", "modern", "black", "everyday"}
        assert recommender.tag_boost(o, taste) == pytest.approx(
            2 * recommender.settings.tag_affinity_boost
        )

    def test_multiword_tag_matches_tokenized_taste(self):
        # profile_text is tokenized word-by-word, so "old money" arrives
        # as {"old", "money"} — the tag should still match
        o = self._outfit(style=["old money"])
        assert recommender.tag_boost(o, {"old", "money"}) == pytest.approx(
            recommender.settings.tag_affinity_boost
        )

    def test_match_is_case_insensitive(self):
        o = self._outfit(style=["Minimal"])
        assert recommender.tag_boost(o, {"minimal"}) > 0


# ---------------------------------------------------------------------------
# Explanations
# ---------------------------------------------------------------------------

class TestExplain:
    def _outfit(self, style=(), color=()):
        return SimpleNamespace(style_tags=list(style), color_tags=list(color))

    def test_two_overlapping_tags(self):
        msg = recommender.explain(
            self._outfit(style=["minimal", "modern"]), {"minimal", "modern"}
        )
        assert msg == "Recommended because you like minimal and modern pieces."

    def test_single_overlapping_tag(self):
        msg = recommender.explain(self._outfit(style=["minimal"]), {"minimal"})
        assert msg == "Recommended because you like minimal styles."

    def test_no_overlap_falls_back_to_first_tag(self):
        msg = recommender.explain(self._outfit(style=["vintage"]), {"minimal"})
        assert msg == "A close visual match to your taste profile, with vintage influences."

    def test_no_tags_at_all(self):
        msg = recommender.explain(self._outfit(), {"minimal"})
        assert msg == "A close visual match to your taste profile."

    def test_overlap_is_case_insensitive(self):
        msg = recommender.explain(self._outfit(style=["Minimal"]), {"minimal"})
        assert msg == "Recommended because you like Minimal styles."
