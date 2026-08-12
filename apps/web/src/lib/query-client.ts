import { QueryClient, type DefaultOptions } from '@tanstack/react-query';
import axios from 'axios';

const defaultOptions: DefaultOptions = {
  queries: {
    // School data changes on human timescales; a short window kills most
    // duplicate fetches during navigation without serving stale figures.
    staleTime: 30_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    retry: (failureCount, error) => {
      // Never retry a client error — a 400/403/404 will not fix itself, and
      // retrying a 401 would race the token refresh interceptor.
      if (axios.isAxiosError(error)) {
        const status = error.response?.status;
        if (status && status >= 400 && status < 500) return false;
      }
      return failureCount < 2;
    },
  },
  mutations: {
    retry: false,
  },
};

/** One client per browser session; recreated per request on the server. */
export function makeQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions });
}

let browserQueryClient: QueryClient | undefined;

export function getQueryClient(): QueryClient {
  if (typeof window === 'undefined') return makeQueryClient();
  browserQueryClient ??= makeQueryClient();
  return browserQueryClient;
}
