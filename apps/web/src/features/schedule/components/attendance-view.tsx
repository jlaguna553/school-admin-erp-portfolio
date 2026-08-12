'use client';

import { CalendarOff, Check, Loader2 } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useSession } from '@/features/auth/api/use-auth';
import { toApiError } from '@/lib/api-client';
import type { AttendanceStatus } from '@erp/api-types';

import { useDayClasses, useRoll, useTakeRoll } from '../api/use-schedule';
import { toClock } from '../weekdays';

/** The four marks, in the order a register is read: attended, then not. */
const STATUSES: AttendanceStatus[] = ['present', 'late', 'absent', 'excused'];

function todayISO(): string {
  const now = new Date();
  // Local midnight, not UTC: a register belongs to the school's day.
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

/**
 * Taking the roll: the day's classes on the left, the register on the right.
 *
 * The screen opens on today and on nothing selected, because the first question
 * is "which of today's classes have I not done yet" — answered by the list, in
 * one request, rather than by opening each register to find out.
 *
 * An unmarked student is left unmarked. The tempting default — everyone present,
 * mark the absentees — would write attendance records for a roll nobody took,
 * and the two are the same row afterwards. So saving submits only what has been
 * touched, and the counter says how many are still unrecorded.
 */
export function AttendanceView() {
  const t = useTranslations('attendance');
  const tc = useTranslations('common');
  const locale = useLocale();
  const { user } = useSession();

  const [date, setDate] = useState(todayISO());
  const [slotId, setSlotId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, AttendanceStatus>>({});

  const mine = user?.role === 'teacher' ? user.id : undefined;
  const { data: classes = [], isPending: classesPending } = useDayClasses({
    date,
    teacher: mine,
  });
  const { data: roll, isPending: rollPending } = useRoll(slotId, date);
  const take = useTakeRoll();

  // A different class or a different day is a different register; anything
  // typed against the previous one is dropped rather than submitted to it.
  useEffect(() => setDraft({}), [slotId, date]);
  useEffect(() => setSlotId(null), [date]);

  const dateLabel = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, { dateStyle: 'full', timeZone: 'UTC' }).format(
        new Date(`${date}T00:00:00Z`),
      ),
    [date, locale],
  );

  const rows = roll?.rows ?? [];
  const marked = rows.filter((row) => draft[row.enrollment_id] ?? row.status).length;
  const cancelled = roll?.session?.status === 'cancelled';

  async function save(status: 'held' | 'cancelled' = 'held') {
    if (!slotId) return;
    const entries =
      status === 'cancelled'
        ? []
        : rows
            .map((row) => ({
              enrollment_id: row.enrollment_id,
              status: draft[row.enrollment_id] ?? row.status ?? null,
            }))
            // Never invent a mark for somebody nobody looked at.
            .filter((entry) => entry.status !== null);

    try {
      await take.mutateAsync({ slot: slotId, date, status, entries });
      setDraft({});
      toast.success(status === 'cancelled' ? t('classCancelled') : t('rollSaved'));
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title={t('title')} description={t('subtitle')} />

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="roll-date" className="mb-1 block text-xs text-muted-foreground">
            {t('date')}
          </label>
          <Input
            id="roll-date"
            type="date"
            className="w-44"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </div>
        <p className="pb-2 text-sm text-muted-foreground">{dateLabel}</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
        <section aria-labelledby="day-classes" className="space-y-2">
          <h2 id="day-classes" className="text-sm font-medium">
            {t('classesToday')}
          </h2>

          {classesPending ? (
            <Skeleton className="h-40" />
          ) : classes.length === 0 ? (
            <p className="rounded-md border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
              {t('noClasses')}
            </p>
          ) : (
            <ul className="divide-y divide-border overflow-hidden rounded-md border border-border bg-card">
              {classes.map((item) => (
                <li key={item.slot.id}>
                  <button
                    type="button"
                    onClick={() => setSlotId(item.slot.id)}
                    aria-current={slotId === item.slot.id}
                    className={`w-full px-3 py-2 text-left transition-colors hover:bg-muted ${
                      slotId === item.slot.id ? 'bg-muted' : ''
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="tabular text-xs text-muted-foreground">
                        {toClock(item.slot.start_time)}–{toClock(item.slot.end_time)}
                      </span>
                      {item.session === null ? (
                        <Badge variant="warning">{t('notTaken')}</Badge>
                      ) : item.session.status === 'cancelled' ? (
                        <Badge variant="neutral">{t('cancelled')}</Badge>
                      ) : (
                        <Badge variant="success">{t('taken')}</Badge>
                      )}
                    </span>
                    <span className="block truncate text-sm font-medium">
                      {item.slot.subject_name}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {item.slot.group_name}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="roll-sheet" className="space-y-3">
          <h2 id="roll-sheet" className="text-sm font-medium">
            {t('register')}
          </h2>

          {!slotId ? (
            <p className="rounded-md border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              {t('pickAClass')}
            </p>
          ) : rollPending ? (
            <Skeleton className="h-64" />
          ) : rows.length === 0 ? (
            <p className="rounded-md border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              {t('emptyGroup')}
            </p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={marked === rows.length ? 'success' : 'warning'}>
                  {t('markedCount', { marked, total: rows.length })}
                </Badge>
                {cancelled ? <Badge variant="neutral">{t('cancelled')}</Badge> : null}
                {roll?.session?.taken_by_name ? (
                  <span className="text-xs text-muted-foreground">
                    {t('takenBy', { name: roll.session.taken_by_name })}
                  </span>
                ) : null}
              </div>

              <ul className="divide-y divide-border overflow-hidden rounded-md border border-border bg-card">
                {rows.map((row) => {
                  const current = draft[row.enrollment_id] ?? row.status ?? null;
                  return (
                    <li
                      key={row.enrollment_id}
                      className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                    >
                      <span className="truncate text-sm">{row.student_name}</span>

                      <fieldset className="flex gap-1" disabled={!roll?.can_edit || cancelled}>
                        <legend className="sr-only">{row.student_name}</legend>
                        {STATUSES.map((status) => (
                          <Button
                            key={status}
                            type="button"
                            size="sm"
                            variant={current === status ? 'primary' : 'outline'}
                            aria-pressed={current === status}
                            onClick={() =>
                              setDraft((previous) => ({ ...previous, [row.enrollment_id]: status }))
                            }
                          >
                            {t(`status.${status}`)}
                          </Button>
                        ))}
                      </fieldset>
                    </li>
                  );
                })}
              </ul>

              {roll?.can_edit ? (
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => save('held')} disabled={take.isPending || cancelled}>
                    {take.isPending ? (
                      <Loader2 className="animate-spin" aria-hidden />
                    ) : (
                      <Check aria-hidden />
                    )}
                    {t('saveRoll')}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => save('cancelled')}
                    disabled={take.isPending || cancelled}
                  >
                    <CalendarOff aria-hidden />
                    {t('cancelClass')}
                  </Button>
                </div>
              ) : (
                <Badge variant="neutral">{t('readOnly')}</Badge>
              )}

              <p className="text-xs text-muted-foreground">{t('unmarkedNote')}</p>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
