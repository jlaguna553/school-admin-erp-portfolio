import createNextIntlPlugin from 'next-intl/plugin';
import type { NextConfig } from 'next';

// Points the plugin at the request-scoped i18n config.
const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');

/**
 * On Vercel the API is only reachable through the `/api` rewrite, and the
 * rewrite is baked in at build time. A build without `API_PROXY_TARGET`
 * therefore deploys perfectly green and is completely unable to talk to the
 * backend — every call 308s to a path that does not exist.
 *
 * That failure is invisible until someone tries to log in, so it is turned into
 * a build error instead. Local and Docker builds are unaffected: they reach the
 * API directly on the same hostname at a different port.
 */
if (process.env.VERCEL && !process.env.API_PROXY_TARGET) {
  throw new Error(
    'API_PROXY_TARGET is required for Vercel builds.\n' +
      'Without it no /api rewrite is generated and the deployed app cannot reach ' +
      'the API at all.\n' +
      'Set it in Project Settings > Environment Variables (e.g. ' +
      'https://your-api.onrender.com), then redeploy with the build cache ' +
      'disabled so the rewrite is regenerated.',
  );
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // `@erp/api-types` ships TypeScript source rather than build output, so Next
  // has to compile it alongside the app.
  transpilePackages: ['@erp/api-types'],
  eslint: {
    dirs: ['src'],
  },
  // Set only in the Docker production build. Emits a self-contained server
  // bundle so the runtime image needs neither pnpm nor node_modules.
  ...(process.env.NEXT_OUTPUT === 'standalone'
    ? { output: 'standalone' as const, outputFileTracingRoot: '/repo' }
    : {}),

  /**
   * Optional reverse proxy for `/api`, enabled by setting `API_PROXY_TARGET`.
   *
   * This is how the app is deployed: the browser talks only to this origin, and
   * `/api/*` is forwarded to Django. Two things depend on it.
   *
   * 1. **Auth.** The refresh cookie is host-only, so it is only sent back to the
   *    exact host that set it. Proxying means Django's `Set-Cookie` reaches the
   *    browser as coming from *this* origin — which is why a split deployment
   *    (app on one domain, API on another) would silently lose the session on
   *    every reload.
   * 2. **Multitenancy.** The school is chosen by hostname. Next forwards the
   *    original host as `X-Forwarded-Host`, and Django resolves the tenant from
   *    it when `DJANGO_USE_X_FORWARDED_HOST=True`.
   *
   * Local development leaves this unset and calls the API directly on the same
   * hostname at a different port, which is same-site and therefore also fine.
   */
  ...(process.env.API_PROXY_TARGET
    ? {
        async rewrites() {
          const target = process.env.API_PROXY_TARGET;
          return [
            {
              source: '/api/:path*',
              // The destination re-adds the trailing slash on purpose. Every DRF
              // route ends in one, but `:path*` splits on `/` and discards the
              // empty final segment, so `/api/health/` would otherwise reach
              // Django as `/api/health` and come back as a 301 from
              // APPEND_SLASH — breaking any POST, which cannot follow it.
              destination: `${target}/api/:path*/`,
            },
          ];
        },
        // Stops Next 308-ing the client's trailing slash away before the rewrite
        // is even considered.
        skipTrailingSlashRedirect: true,
      }
    : {}),
};

export default withNextIntl(nextConfig);
