# syntax=docker/dockerfile:1
FROM golang:1.26-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
# CGO disabled + a static binary is what makes the distroless "static"
# base image below work at all -- distroless ships no libc for a
# dynamically-linked binary to link against.
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/ingest-service .

# distroless: no shell, no package manager, no attack surface beyond
# the binary itself -- appropriate for a service that only ever speaks
# HTTP-in/Kafka-out and never needs a shell to do it. :nonroot runs as
# UID 65532 by default.
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/ingest-service /ingest-service
EXPOSE 8081
ENTRYPOINT ["/ingest-service"]
