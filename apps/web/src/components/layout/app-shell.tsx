'use client';

import { useTranslations } from 'next-intl';
import { useEffect, useState, type ReactNode } from 'react';

import { useRouter } from '@/i18n/navigation';
import { Skeleton } from '@/components/ui/skeleton';
import { useSession } from '@/features/auth/api/use-auth';
import { decodeAccessToken, getAccessToken, subscribe } from '@/lib/auth/token-store';
import type { AccessTokenClaims } from '@erp/api-types';

import { canReadModule, isPlatformOperator, type ModuleKey } from '@/lib/access';

import { platformNavItems } from './nav-items';
import { Sidebar } from './sidebar';
import { Topbar } from './topbar';

interface AppShellProps {
  children: ReactNode;
  /** Dictionary key under `nav` naming the current page. */
  titleKey: string;
  /**
   * Which menu to render.
   *
   * A string rather than the item list itself: pages are Server Components, and
   * the nav items carry Lucide icon *components*, which cannot cross the
   * server/client boundary -- passing them serialises a function and fails the
   * render outright.
   */
  nav?: 'school' | 'platform';
  /**
   * What this page needs to be shown at all.
   *
   * `'platform'` restricts it to operators; a module key restricts it to the
   * roles that may read that module at an institution still running it.
   * Anyone else is sent to their own dashboard rather than shown a screen whose
   * every request the API refuses.
   */
  requires?: 'platform' | ModuleKey;
}

/**
 * The authenticated shell: fixed sidebar, top bar, scrolling canvas.
 *
 * Also the client-side gate, for both signing in and reach. It is a
 * convenience, never the security boundary — the API refuses on its own terms
 * whatever the browser renders. What it prevents is the interface lying: a
 * school administrator could open the operator console and be shown its tables
 * and its "new institution" button, every one of which came back 403.
 */
export function AppShell({ children, titleKey, nav = 'school', requires }: AppShellProps) {
  const t = useTranslations('nav');
  const router = useRouter();
  const { user, isAuthenticated, isPending } = useSession();
  const claims = decodeAccessToken(useAccessTokenValue());

  const allowed = !requires || mayEnter(requires, user?.role, claims);

  useEffect(() => {
    if (isPending) return;
    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }
    if (!allowed) {
      // Home rather than a dead end: they are signed in and this is simply not
      // theirs. An operator has no school dashboard, so they go to the console.
      router.replace(isPlatformOperator(claims) ? '/platform' : '/dashboard');
    }
  }, [isPending, isAuthenticated, allowed, claims, router]);

  if (isPending || !isAuthenticated || !allowed) {
    return <AppShellSkeleton />;
  }

  return (
    <div className="flex h-dvh overflow-hidden">
      <div className="hidden lg:block">
        <Sidebar
          role={user?.role}
          tenantName={claims?.tenant_name ?? null}
          modules={claims?.modules}
          items={nav === 'platform' ? platformNavItems : undefined}
        />
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          title={t(titleKey)}
          userName={user?.full_name ?? null}
          userEmail={user?.email ?? null}
          isAuthenticated={isAuthenticated}
        />
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}

function AppShellSkeleton() {
  return (
    <div className="flex h-dvh overflow-hidden">
      <Skeleton className="hidden w-56 rounded-none lg:block" />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="h-14 shrink-0 border-b border-border bg-card" />
        <div className="flex-1 space-y-4 p-6">
          <Skeleton className="h-9 w-64" />
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
          <Skeleton className="h-72" />
        </div>
      </div>
    </div>
  );
}

/**
 * May this person open a page with these requirements?
 *
 * Mirrors the API: an operator is whoever acts on the public schema, and a
 * module needs both the institution to run it and the role to reach it.
 */
function mayEnter(
  requires: 'platform' | ModuleKey,
  role: string | undefined,
  claims: AccessTokenClaims | null,
): boolean {
  if (requires === 'platform') return isPlatformOperator(claims);
  return canReadModule(requires, role, claims?.modules);
}

/** Re-reads the token so a school switch re-evaluates the gate. */
function useAccessTokenValue(): string | null {
  const [token, setToken] = useState<string | null>(() => getAccessToken());
  useEffect(() => {
    setToken(getAccessToken());
    return subscribe(() => setToken(getAccessToken()));
  }, []);
  return token;
}
