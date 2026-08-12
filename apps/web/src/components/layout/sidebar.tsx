'use client';

import { GraduationCap, LogOut } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Link, usePathname } from '@/i18n/navigation';
import { cn } from '@/lib/utils';
import { useLogout } from '@/features/auth/api/use-auth';

import { visibleNavItems, type NavItem } from './nav-items';

interface SidebarProps {
  role: string | undefined;
  tenantName: string | null;
  /** Enabled modules; a switched-off one is not offered to anyone. */
  modules?: string[];
  /** Overrides the school menu -- see `platformNavItems`. */
  items?: NavItem[];
}

export function Sidebar({ role, tenantName, modules, items: override }: SidebarProps) {
  const t = useTranslations('nav');
  const pathname = usePathname();
  const logout = useLogout();
  const items = override ?? visibleNavItems(role, modules);

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col bg-sidebar text-sidebar-foreground">
      {/* Brand block */}
      <div className="flex flex-col items-center gap-2 px-4 py-6">
        <div className="flex size-11 items-center justify-center rounded-xl bg-sidebar-accent">
          <GraduationCap className="size-6" aria-hidden />
        </div>
        <span className="line-clamp-2 text-center text-sm font-medium">
          {tenantName ?? t('appName')}
        </span>
      </div>

      <nav aria-label={t('primary')} className="flex-1 overflow-y-auto px-2">
        <p className="px-3 pb-2 pt-2 text-[11px] font-medium uppercase tracking-wider text-sidebar-muted">
          {t('menu')}
        </p>
        <ul className="space-y-0.5">
          {items.map((item) => {
            // Prefix match so /billing/invoices/42 keeps "Billing" active.
            const isActive =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={isActive ? 'page' : undefined}
                  className={cn(
                    'relative flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-sidebar-accent font-medium text-sidebar-foreground'
                      : 'text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-foreground',
                  )}
                >
                  {/* Left accent bar marks the active item, as in the reference. */}
                  {isActive && (
                    <span
                      aria-hidden
                      className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-primary-foreground"
                    />
                  )}
                  <Icon className="size-4 shrink-0" aria-hidden />
                  <span className="truncate">{t(item.labelKey)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-sidebar-border p-2">
        <button
          type="button"
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          className={cn(
            'flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
            'text-sidebar-muted hover:bg-sidebar-accent hover:text-sidebar-foreground',
            'disabled:opacity-60',
          )}
        >
          <LogOut className="size-4 shrink-0" aria-hidden />
          {t('logout')}
        </button>
      </div>
    </aside>
  );
}
