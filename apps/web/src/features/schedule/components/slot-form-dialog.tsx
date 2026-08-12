'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, Trash2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useEffect, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { FormField, describedBy } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useSubjects } from '@/features/academic/api/use-academic';
import { toApiError, toFieldErrors } from '@/lib/api-client';
import type { StudentGroup, TimetableSlot } from '@erp/api-types';

import { WEEKDAYS } from '../weekdays';
import { useCreateSlot, useDeactivateSlot, useUpdateSlot } from '../api/use-schedule';

function makeSlotSchema(t: (key: string) => string) {
  return z
    .object({
      subject: z.string().min(1, t('required')),
      weekday: z.coerce.number().int().min(1).max(7),
      start_time: z.string().min(1, t('required')),
      end_time: z.string().min(1, t('required')),
      room: z.string().max(64),
    })
    .refine((value) => value.end_time > value.start_time, {
      path: ['end_time'],
      message: t('endTimeAfterStart'),
    });
}

type SlotFormValues = z.infer<ReturnType<typeof makeSlotSchema>>;

interface SlotFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  group: StudentGroup;
  slot?: TimetableSlot | null;
  /** Pre-fills the day when the dialog is opened from a column. */
  defaultWeekday?: number;
}

/**
 * Put a class on the timetable, or move one.
 *
 * Clashes are the API's answer, not this form's: the group, the teacher and the
 * room are all things another screen may have booked a second ago, so the
 * refusal has to come from the database's view of the week. What this does is
 * put each refusal on the field that caused it.
 */
export function SlotFormDialog({
  open,
  onOpenChange,
  group,
  slot = null,
  defaultWeekday = 1,
}: SlotFormDialogProps) {
  const t = useTranslations('schedule');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const { data: subjectPage } = useSubjects({ page_size: 200, ordering: 'code' });
  // A group studies one programme, so offering the whole school's subjects
  // would mostly offer choices the API refuses.
  const subjects = useMemo(
    () => (subjectPage?.results ?? []).filter((row) => row.program === group.program),
    [subjectPage, group.program],
  );

  const createMutation = useCreateSlot();
  const updateMutation = useUpdateSlot();
  const removeMutation = useDeactivateSlot();

  const form = useForm<SlotFormValues>({
    resolver: zodResolver(makeSlotSchema(tv)),
    defaultValues: {
      subject: '',
      weekday: defaultWeekday,
      start_time: '08:00',
      end_time: '09:00',
      room: '',
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      subject: slot?.subject ?? subjects[0]?.id ?? '',
      weekday: slot?.weekday ?? defaultWeekday,
      // The API returns `HH:MM:SS`; a time input wants `HH:MM`.
      start_time: (slot?.start_time ?? '08:00').slice(0, 5),
      end_time: (slot?.end_time ?? '09:00').slice(0, 5),
      room: slot?.room ?? group.room ?? '',
    });
  }, [open, slot, subjects, defaultWeekday, group.room, form]);

  async function onSubmit(values: SlotFormValues) {
    const payload = { ...values, group: group.id };
    try {
      if (slot) {
        await updateMutation.mutateAsync({ id: slot.id, payload });
        toast.success(t('slotUpdated'));
      } else {
        await createMutation.mutateAsync(payload);
        toast.success(t('slotCreated'));
      }
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        // A group clash has nowhere to land — the group is fixed by the screen
        // — so it is shown against the hour, which is what can be changed.
        const target = field === 'group' ? 'start_time' : field;
        if (target in values) {
          form.setError(target as keyof SlotFormValues, { message });
          matched = true;
        }
      }
      if (!matched) toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  async function onRemove() {
    if (!slot) return;
    try {
      await removeMutation.mutateAsync(slot.id);
      toast.success(t('slotRemoved'));
      onOpenChange(false);
    } catch (error) {
      toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  const errors = form.formState.errors;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={tc('cancel')}>
        <DialogHeader>
          <DialogTitle>{slot ? t('editSlot') : t('newSlot')}</DialogTitle>
          <DialogDescription>
            {group.program_code} {group.name}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField id="slot_subject" label={t('subject')} error={errors.subject?.message} required>
            <Select
              value={form.watch('subject')}
              onValueChange={(value) => form.setValue('subject', value, { shouldDirty: true })}
            >
              <SelectTrigger id="slot_subject">
                <SelectValue placeholder={t('selectSubject')} />
              </SelectTrigger>
              <SelectContent>
                {subjects.map((subject) => (
                  <SelectItem key={subject.id} value={subject.id}>
                    {subject.code} · {subject.name}
                    {subject.teacher_name ? ` — ${subject.teacher_name}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          <FormField id="slot_weekday" label={t('weekdayLabel')} required>
            <Select
              value={String(form.watch('weekday'))}
              onValueChange={(value) =>
                form.setValue('weekday', Number(value), { shouldDirty: true })
              }
            >
              <SelectTrigger id="slot_weekday">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {WEEKDAYS.map((day) => (
                  <SelectItem key={day} value={String(day)}>
                    {t(`weekday.${day}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="slot_start"
              label={t('startsAt')}
              error={errors.start_time?.message}
              required
            >
              <Input
                id="slot_start"
                type="time"
                aria-invalid={Boolean(errors.start_time)}
                aria-describedby={describedBy('slot_start', errors.start_time?.message)}
                {...form.register('start_time')}
              />
            </FormField>

            <FormField id="slot_end" label={t('endsAt')} error={errors.end_time?.message} required>
              <Input
                id="slot_end"
                type="time"
                aria-invalid={Boolean(errors.end_time)}
                aria-describedby={describedBy('slot_end', errors.end_time?.message)}
                {...form.register('end_time')}
              />
            </FormField>
          </div>

          <FormField id="slot_room" label={t('room')} error={errors.room?.message}>
            <Input id="slot_room" {...form.register('room')} />
          </FormField>

          <DialogFooter>
            {slot ? (
              <Button
                type="button"
                variant="outline"
                className="mr-auto"
                onClick={onRemove}
                disabled={removeMutation.isPending}
              >
                <Trash2 aria-hidden />
                {tc('remove')}
              </Button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={form.formState.isSubmitting}
            >
              {tc('cancel')}
            </Button>
            <Button type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? <Loader2 className="animate-spin" aria-hidden /> : null}
              {tc('save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
