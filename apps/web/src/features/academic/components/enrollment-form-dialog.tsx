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
import { toApiError, toFieldErrors } from '@/lib/api-client';
import type { Enrollment } from '@erp/api-types';

import {
  useAllAcademicYears,
  useAllPrograms,
  useCreateEnrollment,
  useStudentOptions,
  useUpdateEnrollment,
} from '../api/use-academic';

const ENROLLMENT_STATUSES = ['pending', 'active', 'withdrawn', 'completed'] as const;

function makeEnrollmentSchema(t: (key: string) => string) {
  return z.object({
    student: z.string().min(1, t('required')),
    program: z.string().min(1, t('required')),
    academic_year: z.string().min(1, t('required')),
    status: z.enum(ENROLLMENT_STATUSES),
    enrolled_on: z.string().min(1, t('required')),
  });
}

type EnrollmentFormValues = z.infer<ReturnType<typeof makeEnrollmentSchema>>;

interface EnrollmentFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  enrollment?: Enrollment | null;
}

/**
 * Enrol a student in a programme for an academic year.
 *
 * The prerequisite for invoicing: billing holds no ForeignKey into the academic
 * context, so an invoice references an enrollment by bare UUID and the service
 * layer refuses one that does not exist or is not in a billable state. Nothing
 * can be billed until this record exists.
 */
export function EnrollmentFormDialog({
  open,
  onOpenChange,
  enrollment = null,
}: EnrollmentFormDialogProps) {
  const t = useTranslations('academic');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const createMutation = useCreateEnrollment();
  const updateMutation = useUpdateEnrollment();
  const { data: students = [] } = useStudentOptions();
  const { data: programs = [] } = useAllPrograms();
  const { data: years = [] } = useAllAcademicYears();

  const form = useForm<EnrollmentFormValues>({
    resolver: zodResolver(makeEnrollmentSchema(tv)),
    defaultValues: {
      student: '',
      program: '',
      academic_year: '',
      status: 'active',
      enrolled_on: new Date().toISOString().slice(0, 10),
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      student: enrollment?.student ?? '',
      program: enrollment?.program ?? '',
      // Defaults to the current year when there is one: enrolling into a past
      // year is possible but is never the common case.
      academic_year:
        enrollment?.academic_year ?? years.find((year) => year.is_current)?.id ?? '',
      status: (enrollment?.status as EnrollmentFormValues['status']) ?? 'active',
      enrolled_on: enrollment?.enrolled_on ?? new Date().toISOString().slice(0, 10),
    });
  }, [open, enrollment, years, form]);

  async function onSubmit(values: EnrollmentFormValues) {
    try {
      if (enrollment) {
        await updateMutation.mutateAsync({ id: enrollment.id, payload: values });
        toast.success(t('enrollmentUpdated'));
      } else {
        await createMutation.mutateAsync(values);
        toast.success(t('enrollmentCreated'));
      }
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in values) {
          form.setError(field as keyof EnrollmentFormValues, { message });
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
          <DialogTitle>
            {enrollment ? t('editEnrollment') : t('newEnrollment')}
          </DialogTitle>
          <DialogDescription>{t('enrollmentHint')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField id="student" label={t('student')} error={errors.student?.message} required>
            <Select
              value={form.watch('student')}
              onValueChange={(value) => form.setValue('student', value, { shouldDirty: true })}
            >
              <SelectTrigger id="student">
                <SelectValue placeholder={t('selectStudent')} />
              </SelectTrigger>
              <SelectContent>
                {students.map((student) => (
                  <SelectItem key={student.id} value={student.id}>
                    {student.full_name} · {student.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="program"
              label={t('program')}
              error={errors.program?.message}
              required
            >
              <Select
                value={form.watch('program')}
                onValueChange={(value) => form.setValue('program', value, { shouldDirty: true })}
              >
                <SelectTrigger id="program">
                  <SelectValue placeholder={t('selectProgram')} />
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
              id="academic_year"
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
                <SelectTrigger id="academic_year">
                  <SelectValue placeholder={t('selectYear')} />
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

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="status" label={t('status')} error={errors.status?.message}>
              <Select
                value={form.watch('status')}
                onValueChange={(value) =>
                  form.setValue('status', value as EnrollmentFormValues['status'], {
                    shouldDirty: true,
                  })
                }
              >
                <SelectTrigger id="status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENROLLMENT_STATUSES.map((status) => (
                    <SelectItem key={status} value={status}>
                      {t(`enrollmentStatuses.${status}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>

            <FormField
              id="enrolled_on"
              label={t('enrolledOn')}
              error={errors.enrolled_on?.message}
              required
            >
              <Input
                id="enrolled_on"
                type="date"
                aria-invalid={Boolean(errors.enrolled_on)}
                aria-describedby={describedBy('enrolled_on', errors.enrolled_on?.message)}
                {...form.register('enrolled_on')}
              />
            </FormField>
          </div>

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
              {form.formState.isSubmitting ? (
                <Loader2 className="animate-spin" aria-hidden />
              ) : null}
              {tc('save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
