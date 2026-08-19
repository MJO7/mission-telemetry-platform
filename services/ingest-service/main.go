package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
)

func main() {
	brokers := strings.Split(getEnv("KAFKA_BROKERS", "localhost:9092"), ",")
	port := getEnv("PORT", "8081")

	svc := NewIngestService(brokers)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	svc.runWorkers(ctx, 4)

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", svc.handleHealthz)
	mux.HandleFunc("/stats", svc.handleStats)
	mux.HandleFunc("/v1/ingest", svc.handleIngest)

	srv := &http.Server{Addr: ":" + port, Handler: mux}

	go func() {
		log.Printf("ingest-service listening on :%s (brokers=%v)", port, brokers)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	log.Println("shutting down...")
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()
	_ = srv.Shutdown(shutdownCtx)
	cancel() // stop workers
	_ = svc.Close()
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
