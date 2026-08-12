'use client';

import { Bell, Search } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Avatar, AvatarFallback, initialsFrom } from '@/components/ui/avatar';
import { Input } from '@/components/ui/input';

import { LanguageSwitcher } from './language-switcher';
import { SchoolSwitcher } from './school-switcher';
import { ThemeToggle } from './theme-toggle';

interface TopbarProps {
  title: string;
  userName: string | null;
  userEmail: string | null;
  /** Gates the "which schools can I reach" lookup behind a real session. */
  isAuthenticated?: boolean;
}

export function Topbar({
  title,
  userName,
  userEmail,
  isAuthenticated = false,
}: TopbarProps) {
  const t = useTranslations('common');

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-card px-4 lg:px-6">
      <h1 className="truncate text-sm font-semibold">{title}</h1>

      {/* Centred search, capped so it does not stretch on wide screens. */}
      <div className="relative mx-auto hidden w-full max-w-md md:block">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          type="search"
          placeholder={t('searchPlaceholder')}
          aria-label={t('search')}
          className="h-8 bg-background pl-8 text-xs"
        />
      </div>

      <div className="ml-auto flex items-center gap-2">
        {/* Renders nothing for the single-school accounts that are the norm. */}
        <SchoolSwitcher isAuthenticated={isAuthenticated} />
        <LanguageSwitcher />
        <ThemeToggle />

        <button
          type="button"
          className="relative rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label={t('notifications')}
        >
          <Bell className="size-4" aria-hidden />
        </button>

        <div className="flex items-center gap-2 pl-1">
          <Avatar>
            <AvatarFallback>{initialsFrom(userName ?? userEmail)}</AvatarFallback>
          </Avatar>
          <div className="hidden min-w-0 leading-tight sm:block">
            <p className="truncate text-xs font-medium">{userName ?? '—'}</p>
            <p className="truncate text-[11px] text-muted-foreground">{userEmail}</p>
          </div>
        </div>
      </div>
    </header>
  );
}
