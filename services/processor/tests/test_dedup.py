"""No real Redis needed -- claim()/release() only touch whatever object
they're given, so a tiny fake standing in for redis.asyncio.Redis's
.set()/.delete() contract is enough to test the actual dedup logic."""
from processor.dedup import claim, dedup_key, release


def test_dedup_key_format():
    assert dedup_key("v1", "f1", 42) == "dedup:v1:f1:42"


def test_dedup_key_distinguishes_seq_no():
    assert dedup_key("v1", "f1", 1) != dedup_key("v1", "f1", 2)


class _FakeRedis:
    """Mimics redis.asyncio.Redis.set()'s NX contract: returns a truthy
    value if the key was newly set, a falsy one if it already existed --
    without needing a real Redis server for a test that's really just
    exercising claim()'s own logic."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def set(
        self, key: str, value: str, nx: bool = False, ex: int | None = None
    ) -> bool | None:
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


async def test_claim_first_time_succeeds():
    redis = _FakeRedis()
    assert await claim(redis, "dedup:v1:f1:0") is True


async def test_claim_duplicate_is_rejected():
    redis = _FakeRedis()
    assert await claim(redis, "dedup:v1:f1:0") is True
    assert await claim(redis, "dedup:v1:f1:0") is False


async def test_claim_different_keys_are_independent():
    redis = _FakeRedis()
    assert await claim(redis, "dedup:v1:f1:0") is True
    assert await claim(redis, "dedup:v1:f1:1") is True


async def test_release_allows_reclaiming_key():
    """The scenario this exists for: a message is claimed, fails to
    process (bad data, DB error) and goes to the DLQ, then a human
    replays it later -- release() is what makes that replay actually
    reach processing again instead of being dropped as a "duplicate"
    of an attempt that never wrote anything."""
    redis = _FakeRedis()
    assert await claim(redis, "dedup:v1:f1:0") is True
    await release(redis, "dedup:v1:f1:0")
    assert await claim(redis, "dedup:v1:f1:0") is True


async def test_release_of_unclaimed_key_is_a_no_op():
    redis = _FakeRedis()
    await release(redis, "dedup:v1:f1:0")  # must not raise
    assert await claim(redis, "dedup:v1:f1:0") is True
