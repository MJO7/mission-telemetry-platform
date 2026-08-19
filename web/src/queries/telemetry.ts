import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { TelemetryPage, TelemetrySummaryBucket } from "../api/types";

const PAGE_SIZE = 50;

/** Keyset-paginated raw history -- see docs/adr/0011. Each page's
 * cursor comes from the previous page's response, not anything the
 * client constructs itself. */
export function useTelemetryHistory(flightId: string | undefined) {
  return useInfiniteQuery({
    queryKey: ["telemetry", flightId, "history"],
    queryFn: ({ pageParam }: { pageParam: string | undefined }) => {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
      if (pageParam) params.set("after", pageParam);
      return apiFetch<TelemetryPage>(`/v1/flights/${flightId}/telemetry?${params.toString()}`);
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: flightId !== undefined,
  });
}

/** Continuous-aggregate-backed summary -- see docs/adr/0010. Small and
 * bounded (one row per minute of flight), unlike the raw history, so a
 * plain (non-paginated) query is the right fit. */
export function useTelemetrySummary(flightId: string | undefined) {
  return useQuery({
    queryKey: ["telemetry", flightId, "summary"],
    queryFn: () =>
      apiFetch<TelemetrySummaryBucket[]>(`/v1/flights/${flightId}/telemetry/summary`),
    enabled: flightId !== undefined,
  });
}
