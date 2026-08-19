from app.ws.channels import channel_for_flight, flight_id_from_channel


def test_channel_for_flight_is_namespaced():
    assert channel_for_flight("abc-123") == "telemetry:flight:abc-123"


def test_flight_id_from_channel_round_trips():
    flight_id = "abc-123"
    assert flight_id_from_channel(channel_for_flight(flight_id)) == flight_id
