"""Tag selection from per-outfit z-scores."""

import numpy as np
import pytest

from scripts.retag import AESTHETICS, tags_for


def z_with(**scores) -> np.ndarray:
    """z-score vector with named aesthetics set, everything else at 0."""
    z = np.zeros(len(AESTHETICS), dtype=np.float32)
    for name, val in scores.items():
        z[AESTHETICS.index(name.replace("_", " "))] = val
    return z


class TestTagsFor:
    def test_assigns_aesthetics_above_threshold(self):
        z = z_with(streetwear=2.0, oversized=1.8, preppy=0.1)
        assert set(tags_for(z, [], assign_z=1.5, keep_z=1.0, max_tags=4)) == {
            "streetwear",
            "oversized",
        }

    def test_ordered_strongest_first(self):
        z = z_with(minimal=1.6, monochrome=2.4)
        assert tags_for(z, [], assign_z=1.5, keep_z=1.0, max_tags=4)[0] == "monochrome"

    def test_respects_max_tags(self):
        z = z_with(minimal=3.0, monochrome=2.5, chic=2.2, tailored=2.0)
        assert len(tags_for(z, [], assign_z=1.5, keep_z=1.0, max_tags=2)) == 2

    def test_keeps_original_tag_when_clip_partly_agrees(self):
        # vintage below the assign bar but above the keep bar
        z = z_with(streetwear=2.0, vintage=1.2)
        out = tags_for(z, ["vintage"], assign_z=1.5, keep_z=1.0, max_tags=4)
        assert "vintage" in out and "streetwear" in out

    def test_drops_original_tag_clip_disagrees_with(self):
        """The whole point: query-derived tags that don't match the image go."""
        z = z_with(streetwear=2.0, vintage=-0.5)
        assert "vintage" not in tags_for(z, ["vintage"], assign_z=1.5, keep_z=1.0, max_tags=4)

    def test_never_returns_empty(self):
        z = z_with(chic=0.4)  # nothing clears any bar
        out = tags_for(z, [], assign_z=1.5, keep_z=1.0, max_tags=4)
        assert out == ["chic"]  # falls back to the single best

    def test_unknown_original_tags_ignored(self):
        z = z_with(minimal=2.0)
        out = tags_for(z, ["not-an-aesthetic"], assign_z=1.5, keep_z=1.0, max_tags=4)
        assert out == ["minimal"]

    @pytest.mark.parametrize("assign_z,expected", [(1.0, 3), (1.5, 2), (2.5, 1)])
    def test_stricter_threshold_yields_fewer_tags(self, assign_z, expected):
        z = z_with(minimal=3.0, monochrome=2.0, chic=1.4)
        assert len(tags_for(z, [], assign_z=assign_z, keep_z=9.0, max_tags=4)) == expected
