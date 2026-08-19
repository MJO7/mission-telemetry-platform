"""No DB, no WebSocket needed -- authenticate() is just decode_access_token
plus a bit of shaping, exercised the same way test_security.py exercises
the token functions it wraps."""
import uuid

from app.core.security import create_access_token
from app.ws.auth import authenticate


def test_authenticate_accepts_a_valid_token():
    user_id, org_id = uuid.uuid4(), uuid.uuid4()
    token = create_access_token(user_id=user_id, org_id=org_id, role="engineer")

    user = authenticate(token)

    assert user is not None
    assert user.user_id == str(user_id)
    assert user.org_id == str(org_id)
    assert user.role.value == "engineer"


def test_authenticate_rejects_missing_token():
    assert authenticate(None) is None
    assert authenticate("") is None


def test_authenticate_rejects_tampered_token():
    token = create_access_token(user_id=uuid.uuid4(), org_id=uuid.uuid4(), role="viewer")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert authenticate(tampered) is None
