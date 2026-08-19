package main

import "testing"

func validPacket() Packet {
	return Packet{
		OrgID:     "e9976fe0-9220-4c64-85ea-0f6c96dd7881",
		VehicleID: "a657dbc8-4de8-47ef-8168-1f583e51b0b3",
		FlightID:  "afff370d-5267-4909-8d52-d3fa7847aa7e",
		SeqNo:     0,
		TS:        "2026-08-19T16:00:00Z",
		Phase:     "powered",
	}
}

func TestValidate_AcceptsWellFormedPacket(t *testing.T) {
	if reason := validPacket().Validate(); reason != "" {
		t.Fatalf("expected valid packet to pass, got reason: %q", reason)
	}
}

func TestValidate_RejectsBadOrgID(t *testing.T) {
	p := validPacket()
	p.OrgID = "not-a-uuid"
	if reason := p.Validate(); reason == "" {
		t.Fatal("expected validation to reject a non-UUID org_id")
	}
}

func TestValidate_RejectsBadVehicleID(t *testing.T) {
	p := validPacket()
	p.VehicleID = "12345"
	if reason := p.Validate(); reason == "" {
		t.Fatal("expected validation to reject a non-UUID vehicle_id")
	}
}

func TestValidate_RejectsNegativeSeqNo(t *testing.T) {
	p := validPacket()
	p.SeqNo = -1
	if reason := p.Validate(); reason == "" {
		t.Fatal("expected validation to reject a negative seq_no")
	}
}

func TestValidate_RejectsMalformedTimestamp(t *testing.T) {
	p := validPacket()
	p.TS = "not a timestamp"
	if reason := p.Validate(); reason == "" {
		t.Fatal("expected validation to reject a malformed ts")
	}
}

func TestValidate_RejectsUnknownPhase(t *testing.T) {
	p := validPacket()
	p.Phase = "orbit" // not a real flight phase in app/models/telemetry.py
	if reason := p.Validate(); reason == "" {
		t.Fatal("expected validation to reject an unrecognized phase")
	}
}

func TestValidate_AcceptsEveryRealPhase(t *testing.T) {
	// Mirrors app/models/telemetry.py's FlightPhase enum exactly -- if this
	// ever drifts from the Python side, packets would pass here and then
	// fail to insert once they reach the processor.
	for _, phase := range []string{"pad", "powered", "coasting", "apogee", "drogue", "main", "landed"} {
		p := validPacket()
		p.Phase = phase
		if reason := p.Validate(); reason != "" {
			t.Errorf("expected phase %q to be valid, got reason: %q", phase, reason)
		}
	}
}
