"""No DB needed -- pure functions in app.core.security."""
import uuid

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)


def test_password_hash_rejects_wrong_password():
    h = hash_password("correct horse battery staple")
    assert not verify_password("wrong password", h)


def test_password_hash_is_salted():
    # Two hashes of the same password must differ (argon2 salts by default) --
    # if this ever fails it means salting broke, which would make rainbow
    # tables viable again.
    a = hash_password("same-password")
    b = hash_password("same-password")
    assert a != b


def test_access_token_roundtrip():
    user_id, org_id = uuid.uuid4(), uuid.uuid4()
    token = create_access_token(user_id=user_id, org_id=org_id, role="engineer")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["org_id"] == str(org_id)
    assert payload["role"] == "engineer"


def test_access_token_rejects_tampering():
    user_id, org_id = uuid.uuid4(), uuid.uuid4()
    token = create_access_token(user_id=user_id, org_id=org_id, role="viewer")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)
