import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Loading } from "./components/StatusMessage";
import { ProtectedRoute } from "./auth/ProtectedRoute";

// Code-split every page: the login screen doesn't need the vehicles/
// flights bundle, and vice versa -- each route only ships what it needs.
const LoginPage = lazy(() => import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() =>
  import("./pages/RegisterPage").then((m) => ({ default: m.RegisterPage })),
);
const VehiclesPage = lazy(() =>
  import("./pages/VehiclesPage").then((m) => ({ default: m.VehiclesPage })),
);
const VehicleDetailPage = lazy(() =>
  import("./pages/VehicleDetailPage").then((m) => ({ default: m.VehicleDetailPage })),
);
const FlightsPage = lazy(() =>
  import("./pages/FlightsPage").then((m) => ({ default: m.FlightsPage })),
);
const FlightDetailPage = lazy(() =>
  import("./pages/FlightDetailPage").then((m) => ({ default: m.FlightDetailPage })),
);
const NotFoundPage = lazy(() =>
  import("./pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })),
);

export function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/vehicles" replace />} />
            <Route path="/vehicles" element={<VehiclesPage />} />
            <Route path="/vehicles/:id" element={<VehicleDetailPage />} />
            <Route path="/flights" element={<FlightsPage />} />
            <Route path="/flights/:id" element={<FlightDetailPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
