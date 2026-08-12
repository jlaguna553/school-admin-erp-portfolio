'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchDashboardMetrics } from './dashboard-api';

export const dashboardKeys = {
  metrics: ['dashboard', 'metrics'] as const,
};

export function useDashboardMetrics() {
  return useQuery({
    queryKey: dashboardKeys.metrics,
    queryFn: fetchDashboardMetrics,
    staleTime: 60_000,
  });
}
