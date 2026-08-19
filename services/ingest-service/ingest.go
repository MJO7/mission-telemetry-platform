package main

import (
	"context"
	"encoding/json"
	"log"
	"sync/atomic"
	"time"

	"github.com/segmentio/kafka-go"
)

// IngestService owns the bounded channel that decouples HTTP handlers from
// the Kafka producer, plus the two producers themselves.
//
// Why a channel between HTTP and Kafka at all, instead of writing to Kafka
// directly inside the handler: kafka-go's Writer already batches, but a
// handler that calls WriteMessages directly still blocks the HTTP request
// for however long that write takes. Decoupling means a slow/unavailable
// broker degrades to *dropped packets*, not *hung HTTP requests* -- and
// bounding the channel is what makes that degradation graceful instead of
// an unbounded memory leak. This is the backpressure spec 3.2 asks for.
type IngestService struct {
	ch        chan Packet
	writer    *kafka.Writer
	dlqWriter *kafka.Writer
	dropped   atomic.Int64
	received  atomic.Int64
}

const channelCapacity = 500

func NewIngestService(brokers []string) *IngestService {
	s := &IngestService{
		ch: make(chan Packet, channelCapacity),
		writer: &kafka.Writer{
			Addr:  kafka.TCP(brokers...),
			Topic: "telemetry.raw",
			// Hash on the message key (vehicle_id, set per-message in
			// worker()) so every point from one vehicle lands on the same
			// partition -- see docs/adr/0007 for why that ordering
			// guarantee is the point of partitioning by vehicle_id at all.
			Balancer:     &kafka.Hash{},
			BatchSize:    100,
			BatchTimeout: 50 * time.Millisecond,
			Compression:  kafka.Lz4,
			RequiredAcks: kafka.RequireOne,
		},
		dlqWriter: &kafka.Writer{
			Addr:         kafka.TCP(brokers...),
			Topic:        "telemetry.dlq",
			BatchTimeout: 50 * time.Millisecond,
			Compression:  kafka.Lz4,
			RequiredAcks: kafka.RequireOne,
		},
	}
	return s
}

// dlqRecord is what actually gets published to telemetry.dlq -- the raw
// payload plus *why* it was rejected, so the replay tool (and a human
// deciding whether replay is even worthwhile) doesn't have to guess.
type dlqRecord struct {
	Reason     string          `json:"reason"`
	Payload    json.RawMessage `json:"payload"`
	ReceivedAt time.Time       `json:"received_at"`
}

// enqueue is the non-blocking handoff from an HTTP handler into the
// worker pool. "ok=false" means the channel was full -- the caller sheds
// load (503) rather than blocking the request or growing memory without
// bound. Deliberately not buffering "just a bit more": an unbounded queue
// in front of a struggling broker is the same OOM risk with extra steps.
func (s *IngestService) enqueue(p Packet) (ok bool) {
	s.received.Add(1)
	select {
	case s.ch <- p:
		return true
	default:
		s.dropped.Add(1)
		return false
	}
}

// publishToDLQ is called directly from the HTTP handler (not through the
// channel) for validation failures -- those are rare and small, so the
// synchronous write's latency is an acceptable cost for the simplicity of
// not needing a second channel/worker pool just for the unhappy path.
func (s *IngestService) publishToDLQ(ctx context.Context, reason string, raw json.RawMessage) error {
	rec := dlqRecord{Reason: reason, Payload: raw, ReceivedAt: time.Now().UTC()}
	body, err := json.Marshal(rec)
	if err != nil {
		return err
	}
	return s.dlqWriter.WriteMessages(ctx, kafka.Message{Value: body})
}

// runWorkers starts n goroutines draining the channel into Kafka. Multiple
// workers (not one) so a single slow WriteMessages call doesn't stall the
// whole pipeline -- mirrors the "3-partition consumer group" horizontal
// scaling story on the producer side.
func (s *IngestService) runWorkers(ctx context.Context, n int) {
	for i := 0; i < n; i++ {
		go s.worker(ctx)
	}
}

func (s *IngestService) worker(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case p := <-s.ch:
			body, err := json.Marshal(p)
			if err != nil {
				log.Printf("worker: marshal failed for vehicle=%s seq=%d: %v", p.VehicleID, p.SeqNo, err)
				continue
			}
			msg := kafka.Message{Key: []byte(p.VehicleID), Value: body}
			if err := s.writer.WriteMessages(ctx, msg); err != nil {
				log.Printf("worker: kafka write failed for vehicle=%s seq=%d: %v", p.VehicleID, p.SeqNo, err)
			}
		}
	}
}

func (s *IngestService) Close() error {
	if err := s.writer.Close(); err != nil {
		return err
	}
	return s.dlqWriter.Close()
}
