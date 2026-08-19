# ADR-0005: Generate TypeScript types from OpenAPI, don't hand-write a client

**Status:** Accepted — Phase 2

## Context
`api-service` already emits an OpenAPI schema for free (FastAPI derives
it from the Pydantic models and route signatures). The frontend needs
typed request/response shapes for every endpoint it calls, and those
shapes must not silently drift from what the backend actually returns.

## Decision
`npm run gen:api` runs `openapi-typescript` against the running
backend's `/openapi.json` and writes `web/src/api/schema.d.ts` — pure
type declarations, zero runtime code. `web/src/api/types.ts` re-exports
named aliases (`Vehicle`, `Flight`, `CurrentUser`, …) over that
generated file, and a single hand-written `apiFetch()` wrapper
(`web/src/api/client.ts`) does the actual `fetch` call, auth header
injection, and 401/refresh handling. Regenerating after any backend
schema change is a type-check away from catching every call site that
assumed the old shape.

## Alternatives considered
**A fully generated client** (e.g. `openapi-typescript-codegen`, or
`@hey-api/openapi-ts`'s client mode) that also generates the request
functions themselves, not just the types. This removes the one
hand-written `apiFetch()` function, but adds a heavier code-generation
step and a second layer to understand when something goes wrong
(generated request logic, not just generated types) — for four
endpoints' worth of routes in Phase 1/2, that's more machinery than the
problem needs. The types-only approach gets the actual thing that
matters (frontend/backend shape drift becomes a compile error) without
it. Revisit if the number of endpoints grows enough that hand-writing
each query/mutation hook becomes real, repetitive toil.

**Hand-written interfaces, no generation at all.** Rejected outright:
this is exactly the "frontend and backend silently drift apart"
failure mode generation exists to prevent (spec §3.7). A renamed or
retyped field in a Pydantic model would compile fine on the frontend
and fail at runtime instead of at build time.

## Consequences
`schema.d.ts` is committed (not gitignored) so the frontend type-checks
without a live backend running — but it can go stale if a backend route
changes and nobody re-runs `npm run gen:api` before committing. No CI
step enforces regeneration yet; that's a Phase 8 gap to close (add a CI
check that runs `gen:api` against a spun-up backend and fails the build
on a diff).
