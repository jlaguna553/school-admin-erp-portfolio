import { getRequestConfig } from 'next-intl/server';

import { routing } from './routing';

/**
 * Resolves the dictionary for the request's locale.
 *
 * An unknown or missing locale segment falls back to `defaultLocale` (`es`)
 * rather than throwing, so a stale bookmark renders the app in Spanish instead
 * of a 500.
 */
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = routing.locales.includes(requested as never)
    ? (requested as string)
    : routing.defaultLocale;

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
    // Keep server and client on one clock so hydration matches.
    timeZone: 'UTC',
  };
});
