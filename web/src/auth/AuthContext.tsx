import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { apiFetch, refreshAccessToken as sharedRefresh } from "../api/client";
import { getAccessToken, setAccessToken } from "./tokenStore";
import { decodeAccessToken } from "./jwt";
import type { CurrentUser, LoginRequest, RegisterOrgRequest, TokenResponse } from "../api/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: CurrentUser | null;
  status: AuthStatus;
  login: (body: LoginRequest) => Promise<void>;
  register: (body: RegisterOrgRequest) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function scheduleProactiveRefresh(token: string) {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    const { exp } = decodeAccessToken(token);
    // Refresh 30s ahead of expiry instead of waiting for a real request to
    // 401 -- avoids a user-visible retry on their next click. The 10-minute
    // TTL itself is set server-side (Settings.access_token_ttl_minutes).
    const msUntilRefresh = Math.max(exp * 1000 - Date.now() - 30_000, 0);
    refreshTimer.current = setTimeout(() => {
      void silentRefresh();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, msUntilRefresh);
  }

  /** Shared tail end of "we now have a fresh access token in tokenStore":
   * schedule the next proactive refresh and load the profile it belongs to. */
  async function loadProfileAndSchedule(token: string) {
    scheduleProactiveRefresh(token);
    const profile = await apiFetch<CurrentUser>("/v1/auth/me");
    setUser(profile);
    setStatus("authenticated");
  }

  async function applyToken(token: string) {
    setAccessToken(token);
    await loadProfileAndSchedule(token);
  }

  /** Always goes through client.ts's deduplicated refreshAccessToken --
   * see the comment there for why silentRefresh must never call
   * /v1/auth/refresh directly. */
  async function silentRefresh(): Promise<boolean> {
    const ok = await sharedRefresh();
    if (!ok) return false;
    const token = getAccessToken();
    if (!token) return false;
    await loadProfileAndSchedule(token);
    return true;
  }

  useEffect(() => {
    // On boot there's no access token in memory (by design, see
    // tokenStore.ts) but there may be a valid httpOnly refresh cookie from
    // a previous visit. Try it silently before assuming the user is logged out.
    (async () => {
      const ok = await silentRefresh();
      if (!ok) {
        setAccessToken(null);
        setStatus("anonymous");
      }
    })();
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(body: LoginRequest) {
    const data = await apiFetch<TokenResponse>("/v1/auth/login", {
      method: "POST",
      body,
      skipAuth: true,
    });
    await applyToken(data.access_token);
  }

  async function register(body: RegisterOrgRequest) {
    const data = await apiFetch<TokenResponse>("/v1/auth/register", {
      method: "POST",
      body,
      skipAuth: true,
    });
    await applyToken(data.access_token);
  }

  async function logout() {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    await apiFetch("/v1/auth/logout", { method: "POST" }).catch(() => undefined);
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
  }

  return (
    <AuthContext.Provider value={{ user, status, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
