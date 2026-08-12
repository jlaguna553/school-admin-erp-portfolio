'use client';

import { Languages } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useTransition } from 'react';

import { usePathname, useRouter } from '@/i18n/navigation';
import { routing, type Locale } from '@/i18n/routing';
import { cn } from '@/lib/utils';

/**
 * Switches locale without losing where the user is.
 *
 * `router.replace` on the *same* pathname with a new locale keeps the route,
 * its params and the React Query cache intact — so the session survives the
 * switch, which is the requirement. The Axios `Accept-Language` header follows
 * via the locale effect in `Providers`, so API messages change language too.
 */
export function LanguageSwitcher() {
  const t = useTranslations('common');
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function switchTo(next: Locale) {
    if (next === locale) return;
    startTransition(() => {
      router.replace(pathname, { locale: next });
    });
  }

  return (
    <div
      className="flex items-center gap-1 rounded-md border border-border p-0.5"
      role="group"
      aria-label={t('language')}
    >
      <Languages className="ml-1 size-3.5 text-muted-foreground" aria-hidden />
      {routing.locales.map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => switchTo(code)}
          disabled={isPending}
          aria-pressed={code === locale}
          className={cn(
            'rounded px-1.5 py-0.5 text-xs font-medium uppercase transition-colors',
            code === locale
              ? 'bg-accent text-accent-foreground'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {code}
        </button>
      ))}
    </div>
  );
}
