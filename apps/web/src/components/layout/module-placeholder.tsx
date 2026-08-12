import { Construction } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Card } from '@/components/ui/card';

interface ModulePlaceholderProps {
  /** Key under `nav` naming the module. */
  titleKey: string;
}

/**
 * Stand-in screen for a module that has a route and a nav entry but no UI yet.
 *
 * These exist so the shell is actually navigable: without them every sidebar
 * link is a dead end, and Next's link prefetching fills the console with 404s
 * on the dashboard.
 */
export function ModulePlaceholder({ titleKey }: ModulePlaceholderProps) {
  const t = useTranslations('nav');
  const tc = useTranslations('common');

  return (
    <Card className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <div className="flex size-11 items-center justify-center rounded-xl bg-muted">
        <Construction className="size-5 text-muted-foreground" aria-hidden />
      </div>
      <h2 className="text-lg font-semibold tracking-tight">{t(titleKey)}</h2>
      <p className="max-w-sm text-sm text-muted-foreground">{tc('moduleComingSoon')}</p>
    </Card>
  );
}
