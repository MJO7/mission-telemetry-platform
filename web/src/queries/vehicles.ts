import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { Vehicle, VehicleCreate } from "../api/types";

export function useVehicles() {
  return useQuery({
    queryKey: ["vehicles"],
    queryFn: () => apiFetch<Vehicle[]>("/v1/vehicles"),
  });
}

export function useVehicle(id: string | undefined) {
  return useQuery({
    queryKey: ["vehicles", id],
    queryFn: () => apiFetch<Vehicle>(`/v1/vehicles/${id}`),
    enabled: id !== undefined,
  });
}

export function useCreateVehicle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: VehicleCreate) =>
      apiFetch<Vehicle>("/v1/vehicles", { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["vehicles"] });
    },
  });
}
