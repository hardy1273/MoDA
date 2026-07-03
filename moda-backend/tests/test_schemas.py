import uuid

import pytest
from pydantic import ValidationError

from app.schemas import FeedbackIn, QuizSubmission


class TestFeedbackIn:
    @pytest.mark.parametrize("t", ["like", "dislike", "save", "skip"])
    def test_valid_interaction_types(self, t):
        fb = FeedbackIn(user_id=uuid.uuid4(), outfit_id=uuid.uuid4(), interaction_type=t)
        assert fb.interaction_type == t

    @pytest.mark.parametrize("t", ["love", "LIKE", "", "superlike"])
    def test_invalid_interaction_types_rejected(self, t):
        with pytest.raises(ValidationError):
            FeedbackIn(user_id=uuid.uuid4(), outfit_id=uuid.uuid4(), interaction_type=t)


class TestQuizSubmission:
    def test_all_lists_default_empty(self):
        q = QuizSubmission(user_id=uuid.uuid4())
        assert q.aesthetics == []
        assert q.colors == []
        assert q.fits == []
        assert q.brands == []
        assert q.occasions == []
        assert q.inspirations == []
        assert q.liked_outfit_ids == []
        assert q.disliked_outfit_ids == []
