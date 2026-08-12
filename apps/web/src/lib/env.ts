import { z } from 'zod';

/**
 * Validated public environment.
 *
 * One hostname serves the whole platform, so the API origin is simply this
 * app's own: `/api/*` either is the API or is proxied to it. The school is
 * chosen by the session, not the host, which is why nothing here mentions
 * tenants any more.
 *
 * The refresh cookie still matters. It is `httpOnly; SameSite=Lax`, and a Lax
 * cookie only travels on same-site requests — cookies ignore the *port*, so
 * `localhost:3000` talking to `localhost:8000` is same-site and the cookie is
 * sent. Pointing the app at an API on a different registrable domain gives that
 * up, which is what `NEXT_PUBLIC_API_ORIGIN` warns about below.
 */
const publicEnvSchema = z.object({
  /**
   * Port the API is published on, when it is a separate service on the same
   * hostname. That is the local development shape, and development sets it
   * explicitly (`.env.example`, `docker-compose.yml`).
   *
   * **Empty by default on purpose.** A deployed app reaches the API through a
   * same-origin `/api` proxy, and defaulting to a port meant the browser
   * addressed `https://the-app.vercel.app:8000`, where nothing listens: the
   * request died before leaving the browser and surfaced only as a generic
   * "could not sign in". Same-origin is the safe default; a port is the
   * deliberate local exception.
   */
  NEXT_PUBLIC_API_PORT: z.string().regex(/^\d*$/).default(''),
  /**
   * Absolute override, e.g. for a native client or a local frontend pointed at a
   * remote API. Using it across registrable domains gives up cookie auth and
   * needs `AUTH_REFRESH_IN_BODY=True` on the server.
   */
  NEXT_PUBLIC_API_ORIGIN: z.union([z.literal(''), z.string().url()]).default(''),
});

const parsed = publicEnvSchema.safeParse({
  NEXT_PUBLIC_API_PORT: process.env.NEXT_PUBLIC_API_PORT ?? '',
  NEXT_PUBLIC_API_ORIGIN: process.env.NEXT_PUBLIC_API_ORIGIN ?? '',
});

if (!parsed.success) {
  throw new Error(
    `Invalid public environment:\n${parsed.error.issues
      .map((issue) => `  - ${issue.path.join('.')}: ${issue.message}`)
      .join('\n')}`,
  );
}

export const env = parsed.data;

/**
 * Resolve the API origin for the current request.
 *
 * Called per request rather than once at module load: on the server there is no
 * `window`, and the hostname is only known in the browser.
 */
export function apiOrigin(): string {
  // 1. Explicit absolute origin wins (native clients, or a local frontend
  //    pointed at a remote API).
  if (env.NEXT_PUBLIC_API_ORIGIN) return env.NEXT_PUBLIC_API_ORIGIN;

  // 2. A configured port means the API is a separate service on the same
  //    hostname — the local development setup. Same-site, so the cookie still
  //    travels, because cookies ignore ports.
  if (env.NEXT_PUBLIC_API_PORT && typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:${env.NEXT_PUBLIC_API_PORT}`;
  }

  // 3. No port configured: the API is proxied on this app's own origin, so a
  //    relative base is correct. Building an absolute URL here would drop the
  //    browser's port and silently address :80 instead — which is exactly what
  //    happened when the deployed topology was first tested locally.
  return '';
}
