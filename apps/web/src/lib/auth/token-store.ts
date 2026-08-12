import type { AccessTokenClaims } from '@erp/api-types';

/**
 * Token storage.
 *
 * Neither token is persisted by JavaScript:
 *
 * - The **access token lives in memory only**. It dies with the tab, and no
 *   amount of XSS can read it off disk.
 * - The **refresh token is an httpOnly cookie** set by the API. This module
 *   cannot see it, and neither can an injected script; the browser attaches it
 *   to `/api/v1/auth/` requests automatically. A reload therefore starts
 *   unauthenticated and calls the refresh endpoint to get a new access token.
 *
 * That is the whole point of the design: an XSS payload can act only while the
 * page is open, instead of exfiltrating a long-lived token.
 */

let accessToken: string | null = null;

/** Subscribers are notified whenever auth state changes (login, logout, refresh). */
type Listener = () => void;
const listeners = new Set<Listener>();

function notify(): void {
  for (const listener of listeners) listener();
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  notify();
}

export function clearAccessToken(): void {
  setAccessToken(null);
}

/**
 * Decode the access token payload.
 *
 * Read-only convenience for rendering (which nav items to show, the tenant name
 * in the header). The signature is **not** verified here and must never be
 * trusted for authorization — the API re-checks every claim server-side.
 */
export function decodeAccessToken(token: string | null): AccessTokenClaims | null {
  if (!token) return null;
  const segments = token.split('.');
  const payload = segments[1];
  if (segments.length !== 3 || !payload) return null;

  try {
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    const json = atob(padded);
    // Recover multi-byte UTF-8 characters that atob leaves as raw bytes.
    const decoded = decodeURIComponent(
      Array.from(json, (char) => `%${char.charCodeAt(0).toString(16).padStart(2, '0')}`).join(''),
    );
    return JSON.parse(decoded) as AccessTokenClaims;
  } catch {
    return null;
  }
}

export function isExpired(claims: AccessTokenClaims | null, skewSeconds = 30): boolean {
  if (!claims) return true;
  return claims.exp * 1000 - skewSeconds * 1000 <= Date.now();
}
