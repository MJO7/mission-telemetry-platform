# ADR-0004: Access token kept in memory on the client, never localStorage

**Status:** Accepted — Phase 2

## Context
The backend (ADR-0003) already keeps the refresh token out of JS reach
via an `httpOnly` cookie. The access token is different: it *must* be
readable by client code, because it has to go in the `Authorization`
header on every API call. The question is where that readable value
lives between requests.

## Decision
The access token lives in a plain module-level variable
(`web/src/auth/tokenStore.ts`) — not `localStorage`, not
`sessionStorage`. It exists only in memory for as long as the tab is
open, and is lost on reload. `AuthProvider` covers that gap by calling
`POST /v1/auth/refresh` once on mount, which silently re-issues a fresh
access token from the still-valid `httpOnly` refresh cookie — a real
user never notices the round trip.

A second consequence of tokens rotating on every refresh (ADR-0003):
concurrent 401s from multiple in-flight requests must not each trigger
their own refresh call. `web/src/api/client.ts` coalesces every
concurrent refresh attempt into a single shared in-flight `Promise` —
otherwise a second, near-simultaneous refresh would present a token the
first one had already rotated out from under it, and the backend's
reuse-detection logic (`app/core/refresh.py`) would read that as theft
and revoke the entire session for a legitimate user.

## Alternatives considered
**localStorage.** The obvious "just make it survive a reload" option,
and exactly the mistake ADR-0003 already rejected for the refresh
token, for the same reason: anything in `localStorage` is readable by
any script running on the page. A successful XSS anywhere in the app
would hand an attacker a live, usable credential directly, no extra
step required. The access token's short TTL (10 minutes, set
server-side) limits the blast radius if it *is* ever exposed some other
way — but there's no reason to make it trivially exposable via the most
common client-side vulnerability class.

**A dedicated in-memory cache with persistence via `sessionStorage`.**
Marginally better than `localStorage` (cleared when the tab closes) but
still script-readable for the tab's entire lifetime — doesn't remove
the XSS exposure, just narrows its window slightly. Not worth the
added complexity over the httpOnly-cookie-driven silent refresh, which
removes the exposure category entirely rather than shrinking it.

## Consequences
Every page reload costs one extra network round trip (the silent
refresh) before the app is interactive — invisible in practice, but a
real cost worth naming. Any code that reads the access token must go
through `getAccessToken()`/`setAccessToken()` rather than reaching for
persistent storage directly; there is exactly one place this rule could
be violated, which is the point.
