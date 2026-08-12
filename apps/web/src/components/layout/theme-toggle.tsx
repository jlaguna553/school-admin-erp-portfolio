'use client';

import { Monitor, Moon, Sun } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';

import { cn } from '@/lib/utils';

const options = [
  { value: 'light', icon: Sun, labelKey: 'themeLight' },
  { value: 'dark', icon: Moon, labelKey: 'themeDark' },
  { value: 'system', icon: Monitor, labelKey: 'themeSystem' },
] as const;

export function ThemeToggle() {
  const t = useTranslations('common');
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // The server cannot know the resolved theme, so render the control only after
  // hydration — otherwise the highlighted option would mismatch and warn.
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <div className="h-7 w-[76px] rounded-md border border-border" aria-hidden />;
  }

  return (
    <div
      className="flex items-center gap-0.5 rounded-md border border-border p-0.5"
      role="group"
      aria-label={t('theme')}
    >
      {options.map(({ value, icon: Icon, labelKey }) => (
        <button
          key={value}
          type="button"
          onClick={() => setTheme(value)}
          aria-pressed={theme === value}
          title={t(labelKey)}
          className={cn(
            'rounded p-1 transition-colors',
            theme === value
              ? 'bg-accent text-accent-foreground'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Icon className="size-3.5" aria-hidden />
          <span className="sr-only">{t(labelKey)}</span>
        </button>
      ))}
    </div>
  );
}
