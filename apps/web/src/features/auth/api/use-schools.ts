'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiClient } from '@/lib/api-client';
import { setAccessToken } from '@/lib/auth/token-store';
import type { AvailableSchool, LoginResponse } from '@erp/api-types';

/**
 * The schools the signed-in person can work at, current one included.
 *
 * One entry is the common case and means no switcher is drawn. It is empty for
 * a platform operator, who is above every institution rather than a member of
 * any.
 */
export function useAvailableSchools(enabled: boolean) {
  return useQuery({
    queryKey: ['auth', 'schools'] as const,
    queryFn: async () => {
      const { data } = await apiClient.get<AvailableSchool[]>('/api/v1/auth/schools/');
      return data;
    },
    enabled,
    staleTime: 5 * 60_000,
  });
}

/**
 * Move the session to another school.
 *
 * A token re-issue on the same origin — not a navigation, which is what this
 * used to be when each school had its own hostname and switching therefore
 * meant signing in again.
 *
 * Every cached query is dropped afterwards. They were all answered by the
 * previous school, and showing one school's students under another's name for
 * even a moment would be worse than a blank screen.
 */
export function useSwitchSchool() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (tenantId: string) => {
      const { data } = await apiClient.post<LoginResponse>('/api/v1/auth/switch/', {
        tenant_id: tenantId,
      });
      setAccessToken(data.access);
      return data;
    },
    onSuccess: () => queryClient.clear(),
  });
}
