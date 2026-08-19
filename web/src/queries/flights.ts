import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { Flight, FlightCreate } from "../api/types";

export function useFlights() {
  return useQuery({
    queryKey: ["flights"],
    queryFn: () => apiFetch<Flight[]>("/v1/flights"),
  });
}

export function useFlight(id: string | undefined) {
  return useQuery({
    queryKey: ["flights", id],
    queryFn: () => apiFetch<Flight>(`/v1/flights/${id}`),
    enabled: id !== undefined,
  });
}

export function useCreateFlight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FlightCreate) => apiFetch<Flight>("/v1/flights", { method: "POST", body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["flights"] });
    },
  });
}

export function useDeleteFlight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/v1/flights/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["flights"] });
    },
  });
}
