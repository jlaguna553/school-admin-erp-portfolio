'use client';

import { Building2, Check, ChevronsUpDown, Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { useAvailableSchools, useSwitchSchool } from '@/features/auth/api/use-schools';
import { toApiError } from '@/lib/api-client';
import { cn } from '@/lib/utils';

/**
 * Move between the schools one person works at.
 *
 * One domain serves them all, so this is a real switch rather than a link to
 * another origin: the server re-issues the session against the chosen school
 * and the page stays where it is. Under the old host-per-school model the same
 * action meant signing in again, because the refresh cookie is host-only.
 *
 * Renders nothing for the single-school accounts that are the norm — and for
 * platform operators, who are above every school rather than members of one.
 */
export function SchoolSwitcher({ isAuthenticated }: { isAuthenticated: boolean }) {
  const t = useTranslations('nav');
  const tc = useTranslations('common');
  const [open, setOpen] = useState(false);

  const { data: schools = [] } = useAvailableSchools(isAuthenticated);
  const switchSchool = useSwitchSchool();

  if (schools.length < 2) return null;

  const current = schools.find((school) => school.is_current);

  async function choose(tenantId: string) {
    setOpen(false);
    try {
      const data = await switchSchool.mutateAsync(tenantId);
      toast.success(t('switchedTo', { name: data.tenant.name ?? '' }));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  return (
    <div className="relative">
      <Button
        variant="outline"
        size="sm"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={switchSchool.isPending}
        onClick={() => setOpen((value) => !value)}
        className="gap-1.5"
      >
        {switchSchool.isPending ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <Building2 className="size-3.5" aria-hidden />
        )}
        <span className="max-w-32 truncate">{current?.name ?? t('schools')}</span>
        <ChevronsUpDown className="size-3.5 opacity-60" aria-hidden />
      </Button>

      {open ? (
        <>
          {/* Click-away layer, so the menu closes without a global listener. */}
          <button
            type="button"
            className="fixed inset-0 z-40 cursor-default"
            aria-label={t('closeMenu')}
            onClick={() => setOpen(false)}
          />
          <ul
            role="menu"
            aria-label={t('schools')}
            className="absolute right-0 z-50 mt-1 min-w-56 overflow-hidden rounded-md border border-border bg-card py-1 shadow-lg"
          >
            {schools.map((school) => (
              <li key={school.schema} role="none">
                <button
                  type="button"
                  role="menuitem"
                  aria-current={school.is_current ? 'true' : undefined}
                  disabled={school.is_current}
                  onClick={() => choose(school.tenant_id)}
                  className={cn(
                    'flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors',
                    'hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent',
                    school.is_current && 'font-medium',
                  )}
                >
                  <Check
                    className={cn('size-3.5 shrink-0', !school.is_current && 'opacity-0')}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{school.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {school.role}
                    </span>
                  </span>
                  {/* The school's own colour, so the choice is recognisable
                      before the interface repaints. */}
                  <span
                    aria-hidden
                    className="size-2.5 shrink-0 rounded-full ring-1 ring-border"
                    style={{ backgroundColor: school.brand_color }}
                  />
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
