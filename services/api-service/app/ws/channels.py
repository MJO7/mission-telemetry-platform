"""
One tiny shared thing between fanout.py (subscribes) and kafka_bridge.py
(publishes): the Redis channel name a given flight's live updates travel
on. Pulled out on its own so the two sides can't drift -- a typo'd
prefix in only one of them would mean messages get published into the
void with no error anywhere.
"""

CHANNEL_PREFIX = "telemetry:flight:"


def channel_for_flight(flight_id: str) -> str:
    return f"{CHANNEL_PREFIX}{flight_id}"


def flight_id_from_channel(channel: str) -> str:
    return channel.removeprefix(CHANNEL_PREFIX)
