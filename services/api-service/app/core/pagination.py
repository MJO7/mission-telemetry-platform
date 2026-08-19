"""
Keyset (a.k.a. "seek") pagination for telemetry_points -- see
docs/adr/0011 for why this and not OFFSET/LIMIT.

The cursor is opaque to the client on purpose (an implementation detail
they shouldn't parse or construct themselves): it's just enough to seek
from, encoded so it survives a URL query string.
"""
import base64
import json
from datetime import datetime


def encode_cursor(ts: datetime, seq_no: int) -> str:
    payload = json.dumps([ts.isoformat(), seq_no]).encode()
    return base64.urlsafe_b64encode(payload).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    """Raises ValueError on a malformed cursor -- callers map that to a
    400, not a 500: this is user-suppliable input (a query param), not
    an internal invariant."""
    try:
        ts_str, seq_no = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(ts_str), int(seq_no)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("malformed pagination cursor") from exc
