import { Link, useParams } from "react-router-dom";
import { useFlight } from "../queries/flights";
import { useVehicle } from "../queries/vehicles";
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
      <p className="text-xs text-slate-400">
        This panel shows telemetry as it arrives, not history -- a scrollable log of everything
        this flight has recorded lands once Phase 5's storage/query work is in.
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
