import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { roleAtLeast } from "../auth/jwt";
import { useCreateVehicle, useVehicles } from "../queries/vehicles";
import { EmptyState, ErrorMessage, Loading } from "../components/StatusMessage";

export function VehiclesPage() {
  const { user } = useAuth();
  const { data: vehicles, isLoading, error } = useVehicles();
  const createVehicle = useCreateVehicle();
  const canCreate = user ? roleAtLeast(user.role, "engineer") : false;

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    try {
      await createVehicle.mutateAsync({ name, description: description || null });
      setName("");
      setDescription("");
    } catch {
      setFormError("Couldn't create the vehicle.");
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Vehicles</h1>
        <p className="text-sm text-slate-500">Rockets your organization is tracking.</p>
      </div>

      {canCreate && (
        <form
          onSubmit={handleCreate}
          className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
        >
          <div className="min-w-40 flex-1">
            <label htmlFor="vname" className="mb-1 block text-xs font-medium text-slate-600">
              Name
            </label>
            <input
              id="vname"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>
          <div className="min-w-56 flex-[2]">
            <label htmlFor="vdesc" className="mb-1 block text-xs font-medium text-slate-600">
              Description (optional)
            </label>
            <input
              id="vdesc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
            />
          </div>
          <button
            type="submit"
            disabled={createVehicle.isPending}
            className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {createVehicle.isPending ? "Adding…" : "Add vehicle"}
          </button>
          {formError && <p className="w-full text-sm text-red-600">{formError}</p>}
        </form>
      )}

      {isLoading && <Loading />}
      {error && <ErrorMessage error={error} />}
      {vehicles && vehicles.length === 0 && <EmptyState label="No vehicles yet." />}
      {vehicles && vehicles.length > 0 && (
        <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white">
          {vehicles.map((v) => (
            <li key={v.id}>
              <Link to={`/vehicles/${v.id}`} className="block px-4 py-3 hover:bg-slate-50">
                <p className="text-sm font-medium text-slate-900">{v.name}</p>
                {v.description && <p className="text-sm text-slate-500">{v.description}</p>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
