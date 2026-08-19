# ADR-0001: App-level tenant isolation instead of Postgres RLS

**Status:** Accepted — Phase 1

## Context
Every table below `Organization` needs to guarantee one org's rows are
never visible to another org's requests. Postgres offers `CREATE POLICY`
row-level security as a DB-enforced version of this. FastAPI + async
SQLAlchemy offers a dependency-injection point that can do the same
filtering in application code.

## Decision
Enforce tenant isolation in the application layer: every repository
function/query takes `org_id` explicitly and every router depends on
`require_role(...)`, which resolves `org_id` from the verified JWT. There
is exactly one choke point (`app/core/rbac.get_current_user`) where a
request's org identity is established.

## Alternatives considered
**Postgres RLS.** Closes the isolation gap even against a query that
forgets to filter — strictly safer against a certain class of bug. Rejected
for now because: (1) it requires `SET app.current_org_id` (or an
equivalent `SET LOCAL`) on every connection before use, which is awkward
with SQLAlchemy's async connection pooling — you'd need a
checkout/checkin event listener touching every pooled connection; (2) it
creates a second place tenant logic lives (SQL policies vs. Python code),
which can drift out of sync; (3) at this scale (single Postgres, no raw
SQL escape hatches yet) the app-level guarantee is achievable and testable.

## Consequences
A handler that forgets to filter by `org_id` is a real, live bug class
this does not prevent — worth saying explicitly rather than pretending
otherwise. Revisit this decision if: raw SQL is introduced anywhere, a
new engineer joins who doesn't know the convention, or a security review
flags it. The migration path to RLS later is additive (turn on RLS,
policies mirror the existing `org_id` filters) — this decision doesn't
box us out of it.
