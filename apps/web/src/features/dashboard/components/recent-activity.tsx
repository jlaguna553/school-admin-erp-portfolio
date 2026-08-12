import { Check, Circle, Clock } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableWrapper,
} from '@/components/ui/table';

export type ActivityStatus = 'completed' | 'pending' | 'active';

export interface ActivityEntry {
  id: string;
  actor: string;
  action: string;
  when: string;
  status: ActivityStatus;
}

/** Each status pairs an icon with a word, so it never relies on colour alone. */
const statusPresentation: Record<
  ActivityStatus,
  { variant: 'success' | 'neutral' | 'info'; Icon: typeof Check }
> = {
  completed: { variant: 'success', Icon: Check },
  pending: { variant: 'neutral', Icon: Clock },
  active: { variant: 'info', Icon: Circle },
};

interface RecentActivityProps {
  entries: ActivityEntry[];
}

export function RecentActivity({ entries }: RecentActivityProps) {
  const t = useTranslations('dashboard');

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('recentActivity')}</CardTitle>
      </CardHeader>
      <div className="px-2 pb-3 pt-2">
        <TableWrapper>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">{t('activityColumn')}</TableHead>
                <TableHead scope="col">{t('timeColumn')}</TableHead>
                <TableHead scope="col">{t('statusColumn')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((entry) => {
                const { variant, Icon } = statusPresentation[entry.status];
                return (
                  <TableRow key={entry.id}>
                    {/* `w-full max-w-0` makes this the only shrinkable cell, so
                        the row always fits the card and the text truncates
                        instead of pushing the status column out of view. */}
                    <TableCell className="w-full max-w-0">
                      <span className="block truncate">
                        <span className="font-medium">{entry.actor}</span>{' '}
                        <span className="text-muted-foreground">{entry.action}</span>
                      </span>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {entry.when}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <Badge variant={variant}>
                        <Icon className="size-3" aria-hidden />
                        {t(`status.${entry.status}`)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableWrapper>
      </div>
    </Card>
  );
}
