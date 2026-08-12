import { createNavigation } from 'next-intl/navigation';

import { routing } from './routing';

/**
 * Locale-aware replacements for next/link and next/navigation.
 *
 * Always import `Link`, `useRouter` and `redirect` from here rather than from
 * `next/*` -- these keep the active locale in the path, so navigation never
 * silently drops the user back to Spanish.
 */
export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
