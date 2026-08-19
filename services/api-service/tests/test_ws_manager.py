"""No real WebSocket needed -- ConnectionManager only ever calls
conn.queue.put_nowait() on whatever object connect() handed back, so a
bare sentinel stands in for the actual FastAPI WebSocket."""
from app.ws.manager import ConnectionManager


class _FakeWebSocket:
    """Never actually used by ConnectionManager -- it only touches
    conn.queue -- but Connection's constructor expects *something*."""


async def test_first_connection_for_a_flight_is_flagged():
    manager = ConnectionManager(queue_maxsize=10)
    _, is_first = await manager.connect("flight-1", _FakeWebSocket())
    assert is_first is True


async def test_second_connection_for_the_same_flight_is_not_first():
    manager = ConnectionManager(queue_maxsize=10)
    await manager.connect("flight-1", _FakeWebSocket())
    _, is_first = await manager.connect("flight-1", _FakeWebSocket())
    assert is_first is False


async def test_different_flights_each_see_their_own_first_connection():
    manager = ConnectionManager(queue_maxsize=10)
    _, first_a = await manager.connect("flight-a", _FakeWebSocket())
    _, first_b = await manager.connect("flight-b", _FakeWebSocket())
    assert first_a is True
    assert first_b is True


async def test_disconnect_of_only_connection_is_flagged_last():
    manager = ConnectionManager(queue_maxsize=10)
    conn, _ = await manager.connect("flight-1", _FakeWebSocket())
    is_last = await manager.disconnect("flight-1", conn)
    assert is_last is True


async def test_disconnect_with_another_connection_still_present_is_not_last():
    manager = ConnectionManager(queue_maxsize=10)
    conn_a, _ = await manager.connect("flight-1", _FakeWebSocket())
    await manager.connect("flight-1", _FakeWebSocket())
    is_last = await manager.disconnect("flight-1", conn_a)
    assert is_last is False


async def test_broadcast_local_only_reaches_connections_on_that_flight():
    manager = ConnectionManager(queue_maxsize=10)
    conn_a, _ = await manager.connect("flight-a", _FakeWebSocket())
    conn_b, _ = await manager.connect("flight-b", _FakeWebSocket())

    manager.broadcast_local("flight-a", "hello-a")

    assert conn_a.queue.get_nowait() == "hello-a"
    assert conn_b.queue.empty()


async def test_broadcast_local_reaches_every_connection_on_that_flight():
    manager = ConnectionManager(queue_maxsize=10)
    conn_a, _ = await manager.connect("flight-1", _FakeWebSocket())
    conn_b, _ = await manager.connect("flight-1", _FakeWebSocket())

    manager.broadcast_local("flight-1", "tick")

    assert conn_a.queue.get_nowait() == "tick"
    assert conn_b.queue.get_nowait() == "tick"


async def test_full_queue_drops_instead_of_blocking_or_raising():
    manager = ConnectionManager(queue_maxsize=2)
    conn, _ = await manager.connect("flight-1", _FakeWebSocket())

    manager.broadcast_local("flight-1", "one")
    manager.broadcast_local("flight-1", "two")
    manager.broadcast_local("flight-1", "three")  # queue full -- must be dropped, not raise

    assert conn.dropped == 1
    assert conn.queue.qsize() == 2
    assert conn.queue.get_nowait() == "one"
    assert conn.queue.get_nowait() == "two"


async def test_stats_aggregates_across_flights_and_connections():
    manager = ConnectionManager(queue_maxsize=1)
    conn_a, _ = await manager.connect("flight-a", _FakeWebSocket())
    await manager.connect("flight-b", _FakeWebSocket())

    manager.broadcast_local("flight-a", "one")
    manager.broadcast_local("flight-a", "two")  # drops -- conn_a's queue (size 1) is full

    stats = manager.stats()
    assert stats["flights_watched"] == 2
    assert stats["connections"] == 2
    assert stats["dropped_total"] == 1
    assert conn_a.dropped == 1
