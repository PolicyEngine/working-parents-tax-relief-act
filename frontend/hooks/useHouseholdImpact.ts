import { useQuery } from "@tanstack/react-query";
import { api, shouldRetryHouseholdCalculation } from "@/lib/api";
import { HouseholdRequest, HouseholdImpactResponse } from "@/lib/types";

export function useHouseholdImpact(
  request: HouseholdRequest | null,
  enabled: boolean
) {
  return useQuery<HouseholdImpactResponse>({
    queryKey: ["householdImpact", request],
    queryFn: () => api.calculateHouseholdImpact(request!),
    enabled: enabled && request !== null,
    // Retry only brief gateway failures: a rate-limited calculation would be
    // refused again until the firewall's one-minute window ends.
    retry: shouldRetryHouseholdCalculation,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}
