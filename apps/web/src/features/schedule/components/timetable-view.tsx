'use client';

import { Plus, Users } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useEffect, useMemo, useState } from 'react';

import { PageHeader } from '@/components/layout/page-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useSession } from '@/features/auth/api/use-auth';
import { ADMINISTRATION, type Role } from '@/lib/access';
import type { TimetableSlot } from '@erp/api-types';

import { useGroupOptions, useWeek } from '../api/use-schedule';
import { SCHOOL_WEEK, toClock } from '../weekdays';
import { GroupFormDialog } from './group-form-dialog';
import { SlotFormDialog } from './slot-form-dialog';

/**
 * The week, one column per day.
 *
 * Deliberately not a time-proportional grid. A school day has gaps, split
 * lunches and two-hour labs, and drawing it to scale spends most of the screen
 * on empty space so that a 45-minute class can be visibly shorter than a
 * 60-minute one — a fact nobody reads a timetable to learn. Ordered lists per
 * day answer the actual question, "what is next", and survive a phone.
 *
 * Saturday and Sunday appear only when something is scheduled on them, so the
 * ordinary school week is not two columns of blank.
 */
export function TimetableView() {
  const t = useTranslations('schedule');
  const { user } = useSession();

  const { data: groups = [], isPending: groupsPending } = useGroupOptions();
  const [groupId, setGroupId] = useState('');
  const [editing, setEditing] = useState<TimetableSlot | null>(null);
  const [addingOn, setAddingOn] = useState<number | null>(null);
  const [addingGroup, setAddingGroup] = useState(false);

  useEffect(() => {
    if (!groupId && groups.length) setGroupId(groups[0]!.id);
  }, [groups, groupId]);

  const group = groups.find((row) => row.id === groupId) ?? null;
  const { data: slots = [], isPending } = useWeek({ group: groupId || undefined });

  const canEdit = ADMINISTRATION.includes(user?.role as Role);

  const days = useMemo(() => {
    const weekend = [6, 7].filter((day) => slots.some((slot) => slot.weekday === day));
    return [...SCHOOL_WEEK, ...weekend];
  }, [slots]);

  const byDay = useMemo(() => {
    const map = new Map<number, TimetableSlot[]>();
    for (const slot of slots) {
      map.set(slot.weekday, [...(map.get(slot.weekday) ?? []), slot]);
    }
    for (const list of map.values()) list.sort((a, b) => a.start_time.localeCompare(b.start_time));
    return map;
  }, [slots]);

  return (
    <div className="space-y-5">
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          canEdit ? (
            <Button variant="outline" onClick={() => setAddingGroup(true)}>
              <Users aria-hidden />
              {t('newGroup')}
            </Button>
          ) : null
        }
      />

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56">
          <label htmlFor="tt-group" className="mb-1 block text-xs text-muted-foreground">
            {t('group')}
          </label>
          <Select value={groupId} onValueChange={setGroupId}>
            <SelectTrigger id="tt-group">
              <SelectValue placeholder={t('selectGroup')} />
            </SelectTrigger>
            <SelectContent>
              {groups.map((row) => (
                <SelectItem key={row.id} value={row.id}>
                  {row.program_code} {row.name} · {row.academic_year_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {group ? (
          <Badge variant="outline">
            {t('studentCount', { count: group.student_count })}
          </Badge>
        ) : null}
        {group?.tutor_name ? <Badge variant="neutral">{group.tutor_name}</Badge> : null}
      </div>

      {groupsPending || isPending ? (
        <Skeleton className="h-72" />
      ) : groups.length === 0 ? (
        <p className="rounded-md border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          {t('noGroups')}
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {days.map((day) => (
            <section
              key={day}
              className="rounded-md border border-border bg-card"
              aria-labelledby={`day-${day}`}
            >
              <h2
                id={`day-${day}`}
                className="border-b border-border px-3 py-2 text-sm font-medium"
              >
                {t(`weekday.${day}`)}
              </h2>

              <ul className="divide-y divide-border">
                {(byDay.get(day) ?? []).map((slot) => (
                  <li key={slot.id}>
                    <button
                      type="button"
                      disabled={!canEdit}
                      onClick={() => setEditing(slot)}
                      className="w-full px-3 py-2 text-left transition-colors enabled:hover:bg-muted"
                    >
                      <span className="tabular block text-xs text-muted-foreground">
                        {toClock(slot.start_time)}–{toClock(slot.end_time)}
                      </span>
                      <span className="block truncate text-sm font-medium">{slot.subject_name}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {slot.teacher_name ?? t('noTeacher')}
                        {slot.room ? ` · ${slot.room}` : ''}
                      </span>
                    </button>
                  </li>
                ))}

                {(byDay.get(day) ?? []).length === 0 ? (
                  <li className="px-3 py-4 text-center text-xs text-muted-foreground">
                    {t('nothingScheduled')}
                  </li>
                ) : null}
              </ul>

              {canEdit && group ? (
                <div className="border-t border-border p-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full"
                    onClick={() => setAddingOn(day)}
                  >
                    <Plus aria-hidden />
                    {t('addClass')}
                  </Button>
                </div>
              ) : null}
            </section>
          ))}
        </div>
      )}

      {group ? (
        <>
          <SlotFormDialog
            open={addingOn !== null}
            onOpenChange={(open) => setAddingOn(open ? addingOn : null)}
            group={group}
            defaultWeekday={addingOn ?? 1}
          />
          <SlotFormDialog
            open={editing !== null}
            onOpenChange={(open) => setEditing(open ? editing : null)}
            group={group}
            slot={editing}
          />
        </>
      ) : null}

      <GroupFormDialog open={addingGroup} onOpenChange={setAddingGroup} />
    </div>
  );
}
