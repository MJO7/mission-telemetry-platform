import { getAccessToken, setAccessToken } from "../auth/tokenStore";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
}

/**
 * Concurrent 401s must share ONE refresh call, not fire one each.
 *
 * Why this matters here specifically: refresh tokens rotate on every use
 * (backend ADR-0003) -- presenting an already-rotated token is treated
 * as theft and revokes the whole session (app/core/refresh.py). If two
 * requests both 401 at the same moment and each independently calls
 * /v1/auth/refresh, the second call presents a token the first call
 * already rotated out from under it -- the backend reads that as replay
 * and logs the session out entirely, for a perfectly legitimate user.
 * Coalescing into a single in-flight promise means every concurrent 401
 * waits on and reuses the same refresh, so exactly one rotation happens.
 */
let refreshInFlight: Promise<boolean> | null = null;

/**
 * Exported (not just used internally by apiFetch's 401 handler) so that
 * AuthProvider's own mount-time "is there a valid session?" check goes
 * through this exact same in-flight-deduplicated path, instead of making
 * its own independent fetch. That's not just tidiness: React can invoke a
 * mount effect twice in development (StrictMode) or on a fast remount in
 * production, and without sharing this dedup, two concurrent refresh
 * calls would both present the same not-yet-rotated cookie -- the second
 * one to land gets read as replay by app/core/refresh.py and revokes the
 * entire session family, logging the user out for a bug, not an attack.
 */
export async function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${BASE_URL}/v1/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) {
          setAccessToken(null);
          return false;
        }
        const data = (await res.json()) as { access_token: string };
        setAccessToken(data.access_token);
        return true;
      } catch {
        setAccessToken(null);
        return false;
      } finally {
        // Let the next 401 (if any) trigger its own fresh refresh.
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

interface RequestOptions {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  /** Login/register are unauthenticated by definition -- skip the auth
   * header and the 401-triggered refresh loop for them. */
  skipAuth?: boolean;
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
  isRetry = false,
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (!options.skipAuth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    // Sends/receives the httpOnly refresh_token cookie (scoped to
    // /v1/auth server-side) even though this client never reads it.
    credentials: "include",
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 401 && !options.skipAuth && !isRetry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch<T>(path, options, true);
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
