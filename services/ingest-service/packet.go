package main

import (
	"fmt"
	"time"

	"github.com/google/uuid"
)

// validPhases mirrors app/models/telemetry.py's FlightPhase enum exactly --
// the ingest service and the Postgres schema must agree on what a valid
// phase string is, or a packet that passes validation here would fail to
// insert downstream in the processor.
var validPhases = map[string]bool{
	"pad": true, "powered": true, "coasting": true, "apogee": true,
	"drogue": true, "main": true, "landed": true,
}

// Packet is one telemetry sample from a vehicle. Field names/types mirror
// app/models/telemetry.py's TelemetryPoint so the processor can insert one
// of these directly once it's past the org_id/vehicle_id lookup.
//
// OrgID travels in the payload rather than an Authorization header on
// purpose, for now: a real device auth scheme (per-vehicle API keys) is a
// Phase 8+ concern, not something Phase 3's actual learning focus --
// Kafka, Go, idempotent delivery -- needs solved to be real. Named here
// instead of silently assumed: this is not production-ready device auth.
type Packet struct {
	OrgID     string   `json:"org_id"`
	VehicleID string   `json:"vehicle_id"`
	FlightID  string   `json:"flight_id"`
	SeqNo     int64    `json:"seq_no"`
	TS        string   `json:"ts"` // RFC3339
	Phase     string   `json:"phase"`
	AltFt     float64  `json:"alt_ft"`
	VelFtS    float64  `json:"vel_ft_s"`
	AccelG    float64  `json:"accel_g"`
	Qw        float64  `json:"qw"`
	Qx        float64  `json:"qx"`
	Qy        float64  `json:"qy"`
	Qz        float64  `json:"qz"`
	Lat       *float64 `json:"lat,omitempty"`
	Lon       *float64 `json:"lon,omitempty"`
	TempC     *float64 `json:"temp_c,omitempty"`
	BatteryV  *float64 `json:"battery_v,omitempty"`
	RSSI      *int     `json:"rssi,omitempty"`
}

// Validate returns a human-readable reason the packet is invalid, or ""
// if it's clean. A plain string return (not an error type) because the
// caller needs this exact text for two different purposes -- the DLQ
// record and the 422 response -- and stringly-typed is fine for a reason
// that's read by a human, not branched on by code.
func (p Packet) Validate() string {
	if _, err := uuid.Parse(p.OrgID); err != nil {
		return "org_id is not a valid UUID"
	}
	if _, err := uuid.Parse(p.VehicleID); err != nil {
		return "vehicle_id is not a valid UUID"
	}
	if _, err := uuid.Parse(p.FlightID); err != nil {
		return "flight_id is not a valid UUID"
	}
	if p.SeqNo < 0 {
		return "seq_no must be >= 0"
	}
	if _, err := time.Parse(time.RFC3339, p.TS); err != nil {
		return "ts is not a valid RFC3339 timestamp"
	}
	if !validPhases[p.Phase] {
		return fmt.Sprintf("phase %q is not a recognized flight phase", p.Phase)
	}
	return ""
}
