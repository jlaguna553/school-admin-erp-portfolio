import { defineRouting } from 'next-intl/routing';

/**
 * Locale routing. Spanish is the default and, per `localePrefix: 'always'`,
 * still carries its prefix (`/es/dashboard`) so every URL is unambiguous and
 * shareable across languages.
 */
export const routing = defineRouting({
  locales: ['es', 'en'],
  defaultLocale: 'es',
  localePrefix: 'always',
});

export type Locale = (typeof routing.locales)[number];

export function isLocale(value: string): value is Locale {
  return (routing.locales as readonly string[]).includes(value);
}
