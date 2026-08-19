import { useEffect, useState } from "react";
import { refreshAccessToken } from "../api/client";
import { getAccessToken } from "../auth/tokenStore";
import { computeBackoffDelay } from "./backoff";
import type { TelemetryEvent } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

export type StreamStatus = "connecting" | "live" | "reconnecting";

/**
 * Live telemetry for one flight over WebSocket, with automatic
 * reconnect (full-jitter exponential backoff, see backoff.ts) so a
 * server restart or a dropped connection recovers on its own instead
 * of leaving the panel dead until the user reloads the page.
 *
 * Deliberately re-reads the access token fresh on every (re)connect
 * attempt, via the same refreshAccessToken() the REST client dedupes
 * through (api/client.ts) -- a socket that's been open for a while can
 * easily outlive the 10-minute access token, and a reconnect is exactly
 * the moment a fresh one is needed anyway.
 */
export function useFlightStream(flightId: string | undefined): {
  latest: TelemetryEvent | null;
  status: StreamStatus;
} {
  const [latest, setLatest] = useState<TelemetryEvent | null>(null);
  const [status, setStatus] = useState<StreamStatus>("connecting");

  useEffect(() => {
    if (!flightId) return;

    let cancelled = false;
    let socket: WebSocket | null = null;
    let attempt = 0;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    async function connect() {
      const token = getAccessToken() ?? ((await refreshAccessToken()) ? getAccessToken() : null);
      if (cancelled) return;
      if (!token) {
        // No valid session to stream with -- back off and try again
        // rather than give up permanently (the user may log in shortly).
        scheduleRetry();
        return;
      }

      setStatus(attempt === 0 ? "connecting" : "reconnecting");
      const wsBase = BASE_URL.replace(/^http/, "ws");
      socket = new WebSocket(`${wsBase}/ws/flights/${flightId}?token=${encodeURIComponent(token)}`);

      socket.onopen = () => {
        attempt = 0;
        if (!cancelled) setStatus("live");
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        if (cancelled) return;
        setLatest(JSON.parse(event.data) as TelemetryEvent);
      };

      socket.onclose = () => {
        socket = null;
        if (cancelled) return;
        setStatus("reconnecting");
        scheduleRetry();
      };

      socket.onerror = () => {
        socket?.close();
      };
    }

    function scheduleRetry() {
      const delay = computeBackoffDelay(attempt);
      attempt += 1;
      retryTimer = setTimeout(() => {
        void connect();
      }, delay);
    }

    void connect();

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close();
    };
  }, [flightId]);

  return { latest, status };
}
