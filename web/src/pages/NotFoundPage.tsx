import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-2 text-center">
      <p className="text-lg font-medium text-slate-900">Page not found</p>
      <Link to="/vehicles" className="text-sm text-amber-700 hover:underline">
        Back to vehicles
      </Link>
    </div>
  );
}
