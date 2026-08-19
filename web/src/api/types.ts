/**
 * Thin, named aliases over the generated OpenAPI schema.
 *
 * Why generate schema.d.ts instead of hand-writing these interfaces: the
 * backend (services/api-service) is the source of truth for these shapes.
 * If a field is renamed or a route's response model changes, regenerating
 * this file (`npm run gen:api`) is a type error at every call site that
 * used the old shape -- frontend and backend can't silently drift apart.
 * See docs/adr/0005-generated-api-types.md.
 */
import type { components } from "./schema";

export type Vehicle = components["schemas"]["VehicleOut"];
export type VehicleCreate = components["schemas"]["VehicleCreate"];
export type Flight = components["schemas"]["FlightOut"];
export type FlightCreate = components["schemas"]["FlightCreate"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type LoginRequest = components["schemas"]["LoginRequest"];
export type RegisterOrgRequest = components["schemas"]["RegisterOrgRequest"];
export type CurrentUser = components["schemas"]["UserOut"];
export type TelemetryPoint = components["schemas"]["TelemetryPointOut"];
export type TelemetryPage = components["schemas"]["TelemetryPageOut"];
export type TelemetrySummaryBucket = components["schemas"]["TelemetrySummaryBucketOut"];
