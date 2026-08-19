"""build_point() is pure -- no DB, Kafka, or Redis needed to test it."""
import uuid

import pytest

from processor.consumer import build_point


def valid_data() -> dict:
    return {
        "org_id": str(uuid.uuid4()),
        "vehicle_id": str(uuid.uuid4()),
        "flight_id": str(uuid.uuid4()),
        "seq_no": 0,
        "ts": "2026-08-19T16:00:00+00:00",
        "phase": "powered",
        "alt_ft": 120.5,
        "vel_ft_s": 300.2,
        "accel_g": 4.1,
        "qw": 1.0,
        "qx": 0.0,
        "qy": 0.0,
        "qz": 0.0,
    }


def test_build_point_accepts_well_formed_data():
    point = build_point(valid_data())
    assert point.seq_no == 0
    assert point.phase.value == "powered"


def test_build_point_accepts_optional_fields_missing():
    data = valid_data()
    point = build_point(data)
    assert point.lat is None
    assert point.battery_v is None


def test_build_point_uses_optional_fields_when_present():
    data = valid_data()
    data["battery_v"] = 7.4
    data["rssi"] = -60
    point = build_point(data)
    assert point.battery_v == 7.4
    assert point.rssi == -60


def test_build_point_rejects_bad_flight_id():
    data = valid_data()
    data["flight_id"] = "not-a-uuid"
    with pytest.raises(ValueError):
        build_point(data)


def test_build_point_rejects_unknown_phase():
    data = valid_data()
    data["phase"] = "orbit"  # not a real FlightPhase
    with pytest.raises(ValueError):
        build_point(data)


def test_build_point_rejects_missing_field():
    data = valid_data()
    del data["alt_ft"]
    with pytest.raises(KeyError):
        build_point(data)
