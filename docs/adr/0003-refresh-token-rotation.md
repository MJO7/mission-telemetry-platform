# ADR-0003: Rotating opaque refresh tokens with reuse detection, in an httpOnly cookie

**Status:** Accepted — Phase 1

## Context
Access tokens (JWT, 10 min TTL) need a way to be renewed without forcing
re-login every 10 minutes, but a long-lived credential needs a
revocation story.

## Decision
- Refresh token is an opaque random value (`secrets.token_urlsafe(32)`),
  never a JWT. Only its SHA-256 hash is stored server-side.
- Every use **rotates** it: the presented token is marked `rotated_at`
  and a new token in the same `family_id` is issued.
- If a token already marked `rotated_at` is presented again, that's a
  replay signal (a legitimate client would hold the newest token, not an
  already-superseded one) — the entire `family_id` is revoked, forcing
  re-login everywhere that login session was active.
- Transport is an `httpOnly`, `Secure` (in non-dev), `SameSite=Lax`
  cookie scoped to `/v1/auth` — never the JSON response body.

## Alternatives considered
**Long-lived JWT, no refresh token at all.** Simplest possible option,
rejected because a JWT can't be revoked before its `exp` without a
server-side blocklist — which is a token store anyway, just tracking the
wrong token (the one you can't easily invalidate).

**Non-rotating refresh token (one token, reused until expiry).** Rejected
because it has no way to distinguish "attacker stole and is using this
token" from "legitimate client using it normally" — theft is invisible
until abuse becomes obvious some other way.

**localStorage instead of httpOnly cookie.** Rejected: localStorage is
readable by any script running on the page, so a successful XSS
immediately exfiltrates the longest-lived credential in the system. An
httpOnly cookie is invisible to `document.cookie`; the tradeoff is
CSRF exposure, mitigated by `SameSite=Lax` (blocks the cookie being sent
on cross-site POST) plus same-origin API deployment.

## Consequences
Client and server must agree on cookie handling (the SPA cannot manually
attach this token to a cross-origin request — by design). Refresh-token
table grows one row per rotation until a cleanup job prunes
expired/revoked rows (not built yet — flag for Phase 8 backlog).
