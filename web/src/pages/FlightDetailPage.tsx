import { Link, useParams } from "react-router-dom";
import { useFlight } from "../queries/flights";
import { useVehicle } from "../queries/vehicles";
import { ErrorMessage, Loading } from "../components/StatusMessage";

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
      <p className="text-xs text-slate-400">
        Telemetry playback isn't built yet -- that lands once ingest (Phase 3) and storage
        (Phase 5) exist to feed it real data.
      </p>
    </div>
  );
}
