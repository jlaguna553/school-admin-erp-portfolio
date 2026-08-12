import { apiClient, refreshAccessTokenOnce } from '@/lib/api-client';
import { clearAccessToken, setAccessToken } from '@/lib/auth/token-store';
import type { LoginResponse, Me } from '@erp/api-types';

export interface LoginCredentials {
  email: string;
  password: string;
}

export async function login(credentials: LoginCredentials): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/api/v1/auth/login/', credentials);
  // Only the access token is in the body; the refresh token arrives as an
  // httpOnly cookie this code cannot read.
  setAccessToken(data.access);
  return data;
}

export async function logout(): Promise<void> {
  try {
    // No body: the server reads the refresh token from the cookie, blacklists it
    // so it cannot be replayed, and expires the cookie.
    await apiClient.post('/api/v1/auth/logout/');
  } finally {
    // Local state is cleared even if the call fails — the user asked to leave.
    clearAccessToken();
  }
}

export async function fetchMe(): Promise<Me> {
  const { data } = await apiClient.get<Me>('/api/v1/users/me/');
  return data;
}

/**
 * Exchange the refresh cookie for a fresh access token on app start.
 *
 * The access token is memory-only, so a reload always begins unauthenticated
 * until this succeeds. A 401 here simply means there is no usable session.
 */
export async function restoreSession(): Promise<boolean> {
  try {
    await refreshAccessTokenOnce();
    return true;
  } catch {
    clearAccessToken();
    return false;
  }
}
