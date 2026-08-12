import { useTranslations } from 'next-intl';

import { Card, CardHeader, CardTitle } from '@/components/ui/card';

export interface CalendarEntry {
  id: string;
  time: string;
  title: string;
}

interface UpcomingEventsProps {
  entries: CalendarEntry[];
}

/**
 * Compact agenda list. Times are pre-formatted by the caller so this stays a
 * presentational component.
 */
export function UpcomingEvents({ entries }: UpcomingEventsProps) {
  const t = useTranslations('dashboard');

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('upcoming')}</CardTitle>
      </CardHeader>
      <div className="px-5 pb-5 pt-3">
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t('noUpcoming')}</p>
        ) : (
          <ul className="space-y-2.5">
            {entries.map((entry) => (
              <li key={entry.id} className="flex gap-3 text-sm">
                <span className="tabular shrink-0 font-medium text-muted-foreground">
                  {entry.time}
                </span>
                <span className="truncate">{entry.title}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
