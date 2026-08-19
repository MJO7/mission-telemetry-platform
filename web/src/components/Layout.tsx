import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  isActive
    ? "font-medium text-amber-700"
    : "text-slate-600 transition-colors hover:text-slate-900";

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-8">
            <span className="font-semibold text-slate-900">Mission Telemetry</span>
            <nav className="flex gap-5 text-sm">
              <NavLink to="/vehicles" className={navLinkClass}>
                Vehicles
              </NavLink>
              <NavLink to="/flights" className={navLinkClass}>
                Flights
              </NavLink>
            </nav>
          </div>
          {user && (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-slate-600">{user.email}</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-slate-600">
                {user.role}
              </span>
              <button
                type="button"
                onClick={() => void logout()}
                className="text-slate-500 transition-colors hover:text-slate-900"
              >
                Log out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
