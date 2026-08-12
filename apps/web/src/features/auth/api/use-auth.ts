'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { useRouter } from '@/i18n/navigation';
import { getAccessToken, subscribe } from '@/lib/auth/token-store';

import {
  fetchMe,
  login,
  logout,
  restoreSession,
  type LoginCredentials,
} from './auth-api';

export const authKeys = {
  me: ['auth', 'me'] as const,
};

/** Re-renders when the in-memory access token changes. */
function useAccessToken(): string | null {
  const [token, setToken] = useState<string | null>(() => getAccessToken());

  useEffect(() => {
    setToken(getAccessToken());
    return subscribe(() => setToken(getAccessToken()));
  }, []);

  return token;
}

/**
 * Restores the session once on mount, then exposes the current user.
 *
 * `isPending` stays true through the refresh attempt so guarded layouts can show
 * a skeleton instead of flashing the login screen on every reload.
 */
export function useSession() {
  const token = useAccessToken();
  const [restoring, setRestoring] = useState(true);

  useEffect(() => {
    let cancelled = false;
    if (getAccessToken()) {
      setRestoring(false);
      return;
    }
    void restoreSession().finally(() => {
      if (!cancelled) setRestoring(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const query = useQuery({
    queryKey: authKeys.me,
    queryFn: fetchMe,
    enabled: Boolean(token),
    staleTime: 5 * 60_000,
  });

  return {
    user: query.data ?? null,
    isAuthenticated: Boolean(token) && Boolean(query.data),
    isPending: restoring || (Boolean(token) && query.isPending),
    error: query.error,
  };
}

export function useLogin() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: (credentials: LoginCredentials) => login(credentials),
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: authKeys.me });
      // The public schema is the platform itself, not a school -- and it has no
      // dashboard, because none of the school modules are routed on that host.
      const isPlatform = data.tenant.schema === 'public';
      router.replace(isPlatform ? '/platform' : '/dashboard');
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      // Drop every cached response: the next user must not see this one's data.
      queryClient.clear();
      router.replace('/login');
    },
  });
}
