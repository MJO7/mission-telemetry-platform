import { ApiError } from "../api/client";

/** Every list/detail view goes through the same four states -- loading,
 * error, empty, populated -- so they read the same way everywhere in the
 * app instead of each page inventing its own "no data" text. */

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <p className="py-8 text-center text-sm text-slate-500">{label}</p>;
}

export function ErrorMessage({ error }: { error: unknown }) {
  const message =
    error instanceof ApiError
      ? apiErrorMessage(error)
      : error instanceof Error
        ? error.message
        : "Something went wrong.";
  return (
    <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {message}
    </p>
  );
}

export function EmptyState({ label }: { label: string }) {
  return (
    <p className="rounded-md border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
      {label}
    </p>
  );
}

function apiErrorMessage(error: ApiError): string {
  if (error.status === 401) return "Your session expired. Please log in again.";
  if (error.status === 403) return "You don't have permission to do that.";
  const detail = (error.body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  return `Request failed (${error.status}).`;
}
