import uuid
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from fastapi import HTTPException

from app import auth
from app.config import get_settings


class TestPasswordHashing:
    def test_roundtrip(self):
        h = auth.hash_password("correct horse battery staple")
        assert h != "correct horse battery staple"
        assert auth.verify_password("correct horse battery staple", h)

    def test_wrong_password_rejected(self):
        h = auth.hash_password("password-one")
        assert not auth.verify_password("password-two", h)

    def test_garbage_hash_rejected_not_raised(self):
        assert not auth.verify_password("anything", "not-a-bcrypt-hash")

    def test_hashes_are_salted(self):
        assert auth.hash_password("same") != auth.hash_password("same")


class TestTokens:
    def test_roundtrip(self):
        uid = uuid.uuid4()
        token = auth.create_access_token(uid)
        assert auth.decode_token(token) == uid

    def test_tampered_token_rejected(self):
        token = auth.create_access_token(uuid.uuid4())
        with pytest.raises(HTTPException) as exc:
            auth.decode_token(token + "x")
        assert exc.value.status_code == 401

    def test_wrong_secret_rejected(self):
        forged = pyjwt.encode(
            {"sub": str(uuid.uuid4())}, "some-other-secret", algorithm="HS256"
        )
        with pytest.raises(HTTPException):
            auth.decode_token(forged)

    def test_expired_token_rejected(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        expired = pyjwt.encode(
            {"sub": str(uuid.uuid4()), "exp": past},
            get_settings().jwt_secret,
            algorithm="HS256",
        )
        with pytest.raises(HTTPException):
            auth.decode_token(expired)

    def test_non_uuid_subject_rejected(self):
        bad = pyjwt.encode(
            {"sub": "not-a-uuid"}, get_settings().jwt_secret, algorithm="HS256"
        )
        with pytest.raises(HTTPException):
            auth.decode_token(bad)
