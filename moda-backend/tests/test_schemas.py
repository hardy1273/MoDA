import uuid

import pytest
from pydantic import ValidationError

from app.schemas import FeedbackIn, LoginIn, QuizSubmission, SignupIn


class TestFeedbackIn:
    @pytest.mark.parametrize("t", ["like", "dislike", "save", "skip"])
    def test_valid_interaction_types(self, t):
        fb = FeedbackIn(outfit_id=uuid.uuid4(), interaction_type=t)
        assert fb.interaction_type == t

    @pytest.mark.parametrize("t", ["love", "LIKE", "", "superlike"])
    def test_invalid_interaction_types_rejected(self, t):
        with pytest.raises(ValidationError):
            FeedbackIn(outfit_id=uuid.uuid4(), interaction_type=t)


class TestQuizSubmission:
    def test_all_lists_default_empty(self):
        q = QuizSubmission()
        assert q.aesthetics == []
        assert q.colors == []
        assert q.fits == []
        assert q.brands == []
        assert q.occasions == []
        assert q.inspirations == []
        assert q.liked_outfit_ids == []
        assert q.disliked_outfit_ids == []


class TestSignupIn:
    def test_valid(self):
        s = SignupIn(email="a@b.com", username="hardit", password="longenough")
        assert s.username == "hardit"

    def test_short_password_rejected(self):
        with pytest.raises(ValidationError):
            SignupIn(email="a@b.com", username="hardit", password="short")

    def test_bad_email_rejected(self):
        with pytest.raises(ValidationError):
            SignupIn(email="not-an-email", username="hardit", password="longenough")


class TestLoginIn:
    def test_valid(self):
        assert LoginIn(email="a@b.com", password="x").email == "a@b.com"
