import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { roleAtLeast } from "../auth/jwt";
import { useCreateFlight, useDeleteFlight, useFlights } from "../queries/flights";
import { useVehicles } from "../queries/vehicles";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusMessage";

export function FlightsPage() {
  const { user } = useAuth();
  const { data: flights, isLoading, error } = useFlights();
  const { data: vehicles } = useVehicles();
  const createFlight = useCreateFlight();
  const deleteFlight = useDeleteFlight();
  const canWrite = user ? roleAtLeast(user.role, "engineer") : false;

  const [vehicleId, setVehicleId] = useState("");
  const [name, setName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await createFlight.mutateAsync({ vehicle_id: vehicleId, name });
      setName("");
    } catch {
      setFormError("Couldn't create the flight.");
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Flights</h1>
        <p className="text-sm text-slate-500">Every flight logged across your vehicles.</p>
      </div>

      {canWrite && (
        <form
          onSubmit={handleCreate}
          className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
        >
          <div className="min-w-48">
            <label htmlFor="fvehicle" className="mb-1 block text-xs font-medium text-slate-600">
              Vehicle
            </label>
            <select
              id="fvehicle"
              required
              value={vehicleId}
              onChange={(e) => setVehicleId(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            >
              <option value="" disabled>
                Select a vehicle…
              </option>
              {vehicles?.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-40 flex-1">
            <label htmlFor="fname" className="mb-1 block text-xs font-medium text-slate-600">
              Flight name
            </label>
            <input
              id="fname"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>
          <button
            type="submit"
            disabled={createFlight.isPending || !vehicles?.length}
            className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {createFlight.isPending ? "Logging…" : "Log flight"}
          </button>
          {!vehicles?.length && <p className="w-full text-xs text-slate-400">Add a vehicle first.</p>}
          {formError && <p className="w-full text-sm text-red-600">{formError}</p>}
        </form>
      )}

      {isLoading && <Loading />}
      {error && <ErrorMessage error={error} />}
      {flights && flights.length === 0 && <EmptyState label="No flights logged yet." />}
      {flights && flights.length > 0 && (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {flights.map((f) => (
            <li key={f.id} className="flex items-center justify-between px-4 py-3 hover:bg-slate-50">
              <Link to={`/flights/${f.id}`} className="text-sm font-medium text-slate-900">
                {f.name}
              </Link>
              <div className="flex items-center gap-3">
                <span className="text-xs uppercase tracking-wide text-slate-500">
                  {f.processing_status}
                </span>
                {canWrite && (
                  <button
                    type="button"
                    onClick={() => void deleteFlight.mutateAsync(f.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
