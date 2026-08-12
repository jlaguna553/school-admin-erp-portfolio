'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useMemo } from 'react';

import { useSession } from '@/features/auth/api/use-auth';
import { useAttendanceTrend } from '@/features/schedule/api/use-schedule';
import { formatNumber } from '@/lib/utils';

import { useDashboardMetrics } from '../api/use-dashboard';
import { KpiCard } from './kpi-card';
import { RecentActivity, type ActivityEntry } from './recent-activity';
import { TrendChart } from './trend-chart';
import { UpcomingEvents, type CalendarEntry } from './upcoming-events';

export function DashboardView() {
  const t = useTranslations('dashboard');
  const locale = useLocale();
  const { user } = useSession();
  const { data, isPending } = useDashboardMetrics();

  const { data: attendance } = useAttendanceTrend(7);

  // Days nobody took a roll are dropped rather than plotted as zero: a weekend
  // or a holiday is not a day of catastrophic attendance, and a line falling to
  // the floor every Saturday would make the chart unreadable and untrue.
  const trend = useMemo(
    () =>
      (attendance ?? [])
        .filter((point) => point.recorded > 0)
        .map((point) => ({ date: point.date, value: point.value })),
    [attendance],
  );

  // Placeholder content for the two secondary cards: the academic calendar and
  // the audit log are not part of this scaffold. Both are marked in the UI copy.
  const events: CalendarEntry[] = [
    { id: '1', time: '10:00', title: t('placeholder.event1') },
    { id: '2', time: '13:00', title: t('placeholder.event2') },
    { id: '3', time: '16:00', title: t('placeholder.event3') },
  ];

  const activity: ActivityEntry[] = [
    {
      id: '1',
      actor: t('placeholder.actor1'),
      action: t('placeholder.action1'),
      when: t('placeholder.when1'),
      status: 'completed',
    },
    {
      id: '2',
      actor: t('placeholder.actor2'),
      action: t('placeholder.action2'),
      when: t('placeholder.when2'),
      status: 'pending',
    },
    {
      id: '3',
      actor: t('placeholder.actor3'),
      action: t('placeholder.action3'),
      when: t('placeholder.when3'),
      status: 'active',
    },
  ];

  const count = (value: number | undefined) =>
    value === undefined ? '—' : formatNumber(value, locale);

  return (
    <div className="space-y-5">
      {/* Page intro */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight lg:text-3xl">
          {t('welcome', { name: user?.first_name ?? '' })}
        </h2>
        <p className="mt-0.5 text-sm text-muted-foreground">{t('welcomeSubtitle')}</p>
      </div>

      {/* KPI row: 4 -> 2 -> 1 across breakpoints */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label={t('kpi.students')}
          value={count(data?.students)}
          caption={t('kpi.studentsCaption')}
          isLoading={isPending}
        />
        <KpiCard
          label={t('kpi.teachers')}
          value={count(data?.teachers)}
          caption={t('kpi.teachersCaption')}
          isLoading={isPending}
        />
        <KpiCard
          label={t('kpi.enrollments')}
          value={count(data?.activeEnrollments)}
          caption={t('kpi.enrollmentsCaption')}
          isLoading={isPending}
        />
        <KpiCard
          label={t('kpi.overdue')}
          value={count(data?.overdueInvoices)}
          caption={t('kpi.overdueCaption')}
          tone={data && data.overdueInvoices > 0 ? 'warning' : 'neutral'}
          isLoading={isPending}
        />
      </div>

      {/* 2fr / 1fr split, collapsing to one column below lg */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <TrendChart
            title={t('attendanceTrend')}
            data={trend}
            unit="%"
            emptyLabel={t('noAttendanceYet')}
          />
        </div>
        <div className="space-y-4">
          <UpcomingEvents entries={events} />
          <RecentActivity entries={activity} />
        </div>
      </div>
    </div>
  );
}
