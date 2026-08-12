import axios, {
  AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';

import { apiOrigin } from './env';
import { clearAccessToken, getAccessToken, setAccessToken } from './auth/token-store';
import type { ApiError } from '@erp/api-types';

/** Locale sent as `Accept-Language`; set by the locale provider on navigation. */
let activeLocale = 'es';

export function setApiLocale(locale: string): void {
  activeLocale = locale;
}

export const apiClient: AxiosInstance = axios.create({
  // baseURL is set per request in the interceptor below, because the API origin
  // is derived from the browser's hostname (see lib/env.ts) and is therefore not
  // known when this module is evaluated on the server.
  timeout: 20_000,
  headers: { 'Content-Type': 'application/json' },
  // Required for the httpOnly refresh cookie to be sent at all.
  withCredentials: true,
});

// --- Request: attach credentials and locale ---------------------------------
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  config.baseURL = apiOrigin();

  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;

  // Explicit header beats the user's stored profile preference server-side, so
  // the language shown in the UI always matches the language of API messages.
  config.headers['Accept-Language'] = activeLocale;
  return config;
});

// --- Response: refresh once on 401, then retry ------------------------------
type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

/**
 * A single in-flight refresh shared by every waiting request.
 *
 * Without this, a page that fires six queries at once on an expired token would
 * send six refresh calls; with rotation enabled, five of them would present an
 * already-rotated token and fail, logging the user out spuriously.
 */
let refreshInFlight: Promise<string> | null = null;

export async function refreshAccessToken(): Promise<string> {
  // A bare axios call, not `apiClient`: the interceptors must not recurse.
  // No body — the refresh token travels as the httpOnly cookie.
  const { data } = await axios.post<{ access: string }>(
    '/api/v1/auth/refresh/',
    {},
    {
      baseURL: apiOrigin(),
      headers: { 'Content-Type': 'application/json' },
      withCredentials: true,
    },
  );

  setAccessToken(data.access);
  return data.access;
}

/** Shared so a caller cannot start a second refresh alongside the interceptor's. */
export function refreshAccessTokenOnce(): Promise<string> {
  refreshInFlight ??= refreshAccessToken().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const config = error.config as RetriableConfig | undefined;
    const status = error.response?.status;

    const isAuthEndpoint = config?.url?.includes('/auth/');
    const canRetry = status === 401 && config && !config._retried && !isAuthEndpoint;

    if (!canRetry) return Promise.reject(error);

    config._retried = true;

    try {
      const access = await refreshAccessTokenOnce();
      config.headers.Authorization = `Bearer ${access}`;
      return apiClient.request(config);
    } catch (refreshError) {
      // Refresh itself failed — the session is genuinely over. The server has
      // already expired the cookie, so only the in-memory token needs clearing.
      clearAccessToken();
      return Promise.reject(refreshError);
    }
  },
);

/**
 * Narrow an unknown thrown value to the API's error envelope.
 *
 * Every backend error has the same shape (`apps.core.exceptions`), so UI code
 * needs exactly one branch for server-reported problems.
 */
export function toApiError(error: unknown): ApiError['error'] | null {
  if (axios.isAxiosError<ApiError>(error) && error.response?.data?.error) {
    return error.response.data.error;
  }
  return null;
}

/** Field-level errors for react-hook-form's `setError`, if the server sent any. */
export function toFieldErrors(error: unknown): Record<string, string> {
  const apiError = toApiError(error);
  if (!apiError?.details) return {};

  return Object.fromEntries(
    Object.entries(apiError.details).map(([field, message]) => [
      field,
      Array.isArray(message) ? (message[0] ?? '') : String(message),
    ]),
  );
}
