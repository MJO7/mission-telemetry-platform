package main

import (
	"encoding/json"
	"io"
	"net/http"
)

func (s *IngestService) handleHealthz(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}

// handleStats exposes the counters that make backpressure visible instead
// of silent -- in a real deployment this is what a dashboard/alert would
// read, not just something to eyeball in a demo.
func (s *IngestService) handleStats(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]int64{
		"received": s.received.Load(),
		"dropped":  s.dropped.Load(),
	})
}

func (s *IngestService) handleIngest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	raw, err := io.ReadAll(io.LimitReader(r.Body, 1<<16)) // 64KB is generous for one sample
	if err != nil {
		http.Error(w, `{"error":"failed to read body"}`, http.StatusBadRequest)
		return
	}

	var p Packet
	if err := json.Unmarshal(raw, &p); err != nil {
		// Not valid JSON at all -- can't even attribute this to a
		// vehicle/flight, so there's nothing structured worth putting in
		// the DLQ beyond the raw bytes themselves.
		_ = s.publishToDLQ(r.Context(), "invalid JSON: "+err.Error(), raw)
		http.Error(w, `{"error":"invalid JSON"}`, http.StatusBadRequest)
		return
	}

	if reason := p.Validate(); reason != "" {
		_ = s.publishToDLQ(r.Context(), reason, raw)
		w.WriteHeader(http.StatusUnprocessableEntity)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": reason})
		return
	}

	if !s.enqueue(p) {
		// Channel full: shed load rather than block or buffer without
		// bound. 503 + Retry-After is the honest signal to the caller --
		// this is not "your data is invalid," it's "try again shortly."
		w.Header().Set("Retry-After", "1")
		w.WriteHeader(http.StatusServiceUnavailable)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "ingest queue full, retry shortly"})
		return
	}

	w.WriteHeader(http.StatusAccepted)
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "accepted"})
}
