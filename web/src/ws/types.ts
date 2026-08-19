/**
 * Hand-written, not generated -- unlike everything in api/types.ts
 * (see docs/adr/0005), this shape doesn't come from OpenAPI at all.
 * FastAPI's OpenAPI generation only covers HTTP routes; the WebSocket
 * route (services/api-service/app/routers/telemetry_ws.py) forwards
 * whatever processor put on telemetry.processed verbatim, so this is a
 * manually-kept mirror of that payload (processor/consumer.py's
 * event_payload). A drift here is a real risk the generated-types ADR
 * doesn't solve for WS -- worth revisiting if this project ever adds a
 * schema registry.
 */
export interface TelemetryEvent {
  vehicle_id: string;
  flight_id: string;
  seq_no: number;
  phase: string;
  alt_ft: number;
  ts: string;
}
