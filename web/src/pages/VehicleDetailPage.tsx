import { Link, useParams } from "react-router-dom";
import { useVehicle } from "../queries/vehicles";
import { useFlights } from "../queries/flights";
import { ErrorMessage, Loading } from "../components/StatusMessage";

export function VehicleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: vehicle, isLoading, error } = useVehicle(id);
  // Phase 1's /v1/flights lists everything in the org (no vehicle_id
  // filter param yet -- fine at this data volume, see flights.py). We
  // filter client-side rather than adding a query param the backend
  // doesn't support yet.
  const { data: flights } = useFlights();

  if (isLoading) return <Loading />;
  if (error) return <ErrorMessage error={error} />;
  if (!vehicle) return null;

  const vehicleFlights = flights?.filter((f) => f.vehicle_id === vehicle.id) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <Link to="/vehicles" className="text-sm text-amber-700 hover:underline">
          ← Vehicles
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-slate-900">{vehicle.name}</h1>
        {vehicle.description && <p className="text-sm text-slate-500">{vehicle.description}</p>}
      </div>
      <div>
        <h2 className="mb-2 text-sm font-medium text-slate-700">Flights</h2>
        {vehicleFlights.length === 0 ? (
          <p className="text-sm text-slate-500">No flights logged for this vehicle yet.</p>
        ) : (
          <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
            {vehicleFlights.map((f) => (
              <li key={f.id}>
                <Link
                  to={`/flights/${f.id}`}
                  className="flex items-center justify-between px-4 py-3 hover:bg-slate-50"
                >
                  <span className="text-sm font-medium text-slate-900">{f.name}</span>
                  <span className="text-xs uppercase tracking-wide text-slate-500">
                    {f.processing_status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
