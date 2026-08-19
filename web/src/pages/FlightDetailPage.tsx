import { Link, useParams } from "react-router-dom";
import { useFlight } from "../queries/flights";
import { useVehicle } from "../queries/vehicles";
import { useTelemetryHistory, useTelemetrySummary } from "../queries/telemetry";
import { ErrorMessage, Loading } from "../components/StatusMessage";
import { useFlightStream, type StreamStatus } from "../ws/useFlightStream";

export function FlightDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: flight, isLoading, error } = useFlight(id);
  const { data: vehicle } = useVehicle(flight?.vehicle_id);

  if (isLoading) return <Loading />;
  if (error) return <ErrorMessage error={error} />;
  if (!flight) return null;

  return (
    <div className="space-y-4">
      <Link to="/flights" className="text-sm text-amber-700 hover:underline">
        ← Flights
      </Link>
      <div>
        <h1 className="text-lg font-semibold text-slate-900">{flight.name}</h1>
        {vehicle && <p className="text-sm text-slate-500">{vehicle.name}</p>}
      </div>
      <dl className="grid grid-cols-2 gap-4 rounded-lg border border-slate-200 bg-white p-4 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-400">Status</dt>
          <dd className="mt-0.5 text-slate-900">{flight.processing_status}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-400">Apogee</dt>
          <dd className="mt-0.5 text-slate-900">
            {flight.apogee_ft != null ? `${flight.apogee_ft} ft` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-slate-400">Max accel</dt>
          <dd className="mt-0.5 text-slate-900">
            {flight.max_accel_g != null ? `${flight.max_accel_g} g` : "—"}
          </dd>
        </div>
      </dl>
      <LiveTelemetryPanel key={flight.id} flightId={flight.id} />
      <TelemetryHistoryPanel key={`${flight.id}-history`} flightId={flight.id} />
      <p className="text-xs text-slate-400">
        History loads a page at a time (keyset-paginated, not offset -- see docs/adr/0011) so it
        stays fast no matter how long this flight ran. It isn't virtualized yet, so a very long
        flight's list will still get long in the DOM -- that's a real, known gap, not solved here.
      </p>
    </div>
  );
}

function LiveTelemetryPanel({ flightId }: { flightId: string }) {
  const { latest, status } = useFlightStream(flightId);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Live telemetry</h2>
        <StreamStatusPill status={status} />
      </div>
      {latest ? (
        <dl className="mt-3 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-400">Phase</dt>
            <dd className="mt-0.5 text-slate-900">{latest.phase}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-400">Altitude</dt>
            <dd className="mt-0.5 text-slate-900">{latest.alt_ft.toFixed(0)} ft</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-400">Seq</dt>
            <dd className="mt-0.5 text-slate-900">{latest.seq_no}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-400">Sample time</dt>
            <dd className="mt-0.5 text-slate-900">{new Date(latest.ts).toLocaleTimeString()}</dd>
          </div>
        </dl>
      ) : (
        <p className="mt-3 text-sm text-slate-400">Waiting for the first telemetry point…</p>
      )}
    </div>
  );
}

function TelemetryHistoryPanel({ flightId }: { flightId: string }) {
  const summary = useTelemetrySummary(flightId);
  const history = useTelemetryHistory(flightId);
  const points = history.data?.pages.flatMap((page) => page.points) ?? [];

  return (
    <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">History</h2>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Per-minute summary
        </h3>
        {summary.isLoading && <p className="text-sm text-slate-400">Loading…</p>}
        {summary.data && summary.data.length === 0 && (
          <p className="text-sm text-slate-400">
            Nothing yet -- the summary refreshes on a 1-minute schedule (docs/adr/0010).
          </p>
        )}
        {summary.data && summary.data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="pb-1 pr-4">Minute</th>
                  <th className="pb-1 pr-4">Avg alt</th>
                  <th className="pb-1 pr-4">Max alt</th>
                  <th className="pb-1 pr-4">Max accel</th>
                  <th className="pb-1">Samples</th>
                </tr>
              </thead>
              <tbody>
                {summary.data.map((bucket) => (
                  <tr key={bucket.bucket} className="border-t border-slate-100">
                    <td className="py-1 pr-4 text-slate-900">
                      {new Date(bucket.bucket).toLocaleTimeString()}
                    </td>
                    <td className="py-1 pr-4 text-slate-900">
                      {bucket.avg_alt_ft?.toFixed(0) ?? "—"} ft
                    </td>
                    <td className="py-1 pr-4 text-slate-900">
                      {bucket.max_alt_ft?.toFixed(0) ?? "—"} ft
                    </td>
                    <td className="py-1 pr-4 text-slate-900">
                      {bucket.max_accel_g?.toFixed(1) ?? "—"} g
                    </td>
                    <td className="py-1 text-slate-500">{bucket.sample_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
          Raw points
        </h3>
        {history.isLoading && <p className="text-sm text-slate-400">Loading…</p>}
        {points.length === 0 && !history.isLoading && (
          <p className="text-sm text-slate-400">No points recorded yet.</p>
        )}
        {points.length > 0 && (
          <ul className="divide-y divide-slate-100 text-sm">
            {points.map((point) => (
              <li key={`${point.seq_no}-${point.ts}`} className="flex justify-between py-1">
                <span className="text-slate-500">
                  #{point.seq_no} · {point.phase}
                </span>
                <span className="text-slate-900">{point.alt_ft.toFixed(0)} ft</span>
                <span className="text-slate-400">{new Date(point.ts).toLocaleTimeString()}</span>
              </li>
            ))}
          </ul>
        )}
        {history.hasNextPage && (
          <button
            type="button"
            onClick={() => void history.fetchNextPage()}
            disabled={history.isFetchingNextPage}
            className="mt-2 text-sm text-amber-700 hover:underline disabled:opacity-50"
          >
            {history.isFetchingNextPage ? "Loading…" : "Load more"}
          </button>
        )}
      </div>
    </div>
  );
}

const STATUS_STYLES: Record<StreamStatus, string> = {
  live: "border-green-200 bg-green-50 text-green-700",
  connecting: "border-slate-200 bg-slate-50 text-slate-600",
  reconnecting: "border-amber-200 bg-amber-50 text-amber-700",
};

const STATUS_DOT: Record<StreamStatus, string> = {
  live: "bg-green-500",
  connecting: "bg-slate-400",
  reconnecting: "bg-amber-500",
};

const STATUS_LABEL: Record<StreamStatus, string> = {
  live: "Live",
  connecting: "Connecting…",
  reconnecting: "Reconnecting…",
};

function StreamStatusPill({ status }: { status: StreamStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[status]}`} />
      {STATUS_LABEL[status]}
    </span>
  );
}
