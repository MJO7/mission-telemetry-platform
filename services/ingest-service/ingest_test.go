package main

import "testing"

// TestEnqueue_DropsWhenChannelFull is the actual backpressure contract
// from spec 3.2: a full channel sheds load and counts it, rather than
// blocking or growing without bound. Deliberately doesn't start any
// workers -- this tests enqueue() in isolation, so it needs no live
// Kafka broker to run.
func TestEnqueue_DropsWhenChannelFull(t *testing.T) {
	s := NewIngestService([]string{"localhost:9092"})

	for i := 0; i < channelCapacity; i++ {
		if !s.enqueue(validPacket()) {
			t.Fatalf("unexpected drop while filling channel (i=%d of %d)", i, channelCapacity)
		}
	}

	if s.enqueue(validPacket()) {
		t.Fatal("expected enqueue to report failure once the channel is full")
	}

	if got := s.dropped.Load(); got != 1 {
		t.Fatalf("expected dropped counter = 1, got %d", got)
	}
	if want := int64(channelCapacity + 1); s.received.Load() != want {
		t.Fatalf("expected received counter = %d, got %d", want, s.received.Load())
	}
}

func TestEnqueue_SucceedsUnderCapacity(t *testing.T) {
	s := NewIngestService([]string{"localhost:9092"})
	if !s.enqueue(validPacket()) {
		t.Fatal("expected enqueue to succeed with room in the channel")
	}
	if s.dropped.Load() != 0 {
		t.Fatalf("expected no drops, got %d", s.dropped.Load())
	}
}
