"""Pure functions -- no DB needed to exercise the cursor encode/decode
contract itself."""
from datetime import datetime, timezone

import pytest

from app.core.pagination import decode_cursor, encode_cursor


def test_cursor_round_trips():
    ts = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
    cursor = encode_cursor(ts, 42)
    decoded_ts, decoded_seq = decode_cursor(cursor)
    assert decoded_ts == ts
    assert decoded_seq == 42


def test_cursor_is_opaque_base64_not_readable_json():
    cursor = encode_cursor(datetime.now(timezone.utc), 1)
    assert "{" not in cursor  # not raw JSON on the wire
    assert cursor.isascii()


def test_decode_rejects_garbage():
    with pytest.raises(ValueError):
        decode_cursor("not-a-real-cursor")


def test_decode_rejects_truncated_valid_base64():
    # Valid base64 (won't raise on decode) but not our [ts, seq_no] shape.
    import base64

    garbage = base64.urlsafe_b64encode(b'"just a string"').decode()
    with pytest.raises(ValueError):
        decode_cursor(garbage)


def test_different_positions_produce_different_cursors():
    ts = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
    assert encode_cursor(ts, 1) != encode_cursor(ts, 2)
