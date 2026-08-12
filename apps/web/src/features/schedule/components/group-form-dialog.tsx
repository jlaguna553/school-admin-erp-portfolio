'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useEffect } from 'react';
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
import { useAllAcademicYears, useAllPrograms } from '@/features/academic/api/use-academic';
import { toApiError, toFieldErrors } from '@/lib/api-client';
import type { StudentGroup } from '@erp/api-types';

import { useCreateGroup, useUpdateGroup } from '../api/use-schedule';

function makeGroupSchema(t: (key: string) => string) {
  return z.object({
    name: z.string().min(1, t('required')).max(64),
    program: z.string().min(1, t('required')),
    academic_year: z.string().min(1, t('required')),
    tutor: z.string(),
    room: z.string().max(64),
  });
}

type GroupFormValues = z.infer<ReturnType<typeof makeGroupSchema>>;

interface GroupFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  group?: StudentGroup | null;
  /** Teachers, for the tutor selector. */
  teachers?: { id: string; full_name: string }[];
}

/**
 * Open or amend a group.
 *
 * A group is what the timetable and the register are built on, so a school with
 * none has both screens available and neither usable — which is the state every
 * freshly provisioned institution starts in.
 */
export function GroupFormDialog({
  open,
  onOpenChange,
  group = null,
  teachers = [],
}: GroupFormDialogProps) {
  const t = useTranslations('schedule');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const { data: years = [] } = useAllAcademicYears();
  const { data: programs = [] } = useAllPrograms();
  const createMutation = useCreateGroup();
  const updateMutation = useUpdateGroup();

  const form = useForm<GroupFormValues>({
    resolver: zodResolver(makeGroupSchema(tv)),
    defaultValues: { name: '', program: '', academic_year: '', tutor: '', room: '' },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: group?.name ?? '',
      program: group?.program ?? programs[0]?.id ?? '',
      academic_year:
        group?.academic_year ?? (years.find((y) => y.is_current) ?? years[0])?.id ?? '',
      tutor: group?.tutor ?? '',
      room: group?.room ?? '',
    });
  }, [open, group, years, programs, form]);

  async function onSubmit(values: GroupFormValues) {
    // An empty selection is "no tutor", which the API spells `null`.
    const payload = { ...values, tutor: values.tutor || null };

    try {
      if (group) {
        await updateMutation.mutateAsync({ id: group.id, payload });
        toast.success(t('groupUpdated'));
      } else {
        await createMutation.mutateAsync(payload);
        toast.success(t('groupCreated'));
      }
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in values) {
          form.setError(field as keyof GroupFormValues, { message });
          matched = true;
        }
      }
      if (!matched) toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  const errors = form.formState.errors;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={tc('cancel')}>
        <DialogHeader>
          <DialogTitle>{group ? t('editGroup') : t('newGroup')}</DialogTitle>
          <DialogDescription>{t('groupHint')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="group_name"
              label={t('groupName')}
              hint={t('groupNameHint')}
              error={errors.name?.message}
              required
            >
              <Input
                id="group_name"
                aria-invalid={Boolean(errors.name)}
                aria-describedby={describedBy('group_name', errors.name?.message)}
                {...form.register('name')}
              />
            </FormField>

            <FormField id="group_room" label={t('homeRoom')} error={errors.room?.message}>
              <Input id="group_room" {...form.register('room')} />
            </FormField>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="group_program" label={t('programme')} error={errors.program?.message} required>
              <Select
                value={form.watch('program')}
                onValueChange={(value) => form.setValue('program', value, { shouldDirty: true })}
              >
                <SelectTrigger id="group_program">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {programs.map((program) => (
                    <SelectItem key={program.id} value={program.id}>
                      {program.code} · {program.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>

            <FormField
              id="group_year"
              label={t('academicYear')}
              error={errors.academic_year?.message}
              required
            >
              <Select
                value={form.watch('academic_year')}
                onValueChange={(value) =>
                  form.setValue('academic_year', value, { shouldDirty: true })
                }
              >
                <SelectTrigger id="group_year">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {years.map((year) => (
                    <SelectItem key={year.id} value={year.id}>
                      {year.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
          </div>

          <FormField id="group_tutor" label={t('tutor')} hint={t('tutorHint')}>
            <Select
              value={form.watch('tutor') || 'none'}
              onValueChange={(value) =>
                form.setValue('tutor', value === 'none' ? '' : value, { shouldDirty: true })
              }
            >
              <SelectTrigger id="group_tutor">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">{t('noTutor')}</SelectItem>
                {teachers.map((teacher) => (
                  <SelectItem key={teacher.id} value={teacher.id}>
                    {teacher.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          <DialogFooter>
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
