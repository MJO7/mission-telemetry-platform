/**
 * Where the access token actually lives on the client: in memory only,
 * never localStorage/sessionStorage.
 *
 * Why: the refresh token already can't be read by JS (httpOnly cookie,
 * see the backend's ADR-0003). The access token CAN be read by JS -- it
 * has to be, to go in the Authorization header -- so the only real
 * protection left is keeping its lifetime short (10 min, set
 * server-side) and never handing it to persistent, script-readable
 * storage. localStorage survives a page reload, which sounds
 * convenient, but it also means an XSS bug anywhere on the page can
 * read it directly, any time, for as long as the page is open.
 *
 * The cost: reloading the page loses the in-memory token. AuthProvider
 * pays that cost invisibly by calling /v1/auth/refresh on mount, which
 * re-issues a fresh access token using the httpOnly cookie -- a real
 * user never notices, and an attacker's injected script never gets a
 * persistent copy worth stealing. See docs/adr/0004-access-token-storage.md.
 */
let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}
