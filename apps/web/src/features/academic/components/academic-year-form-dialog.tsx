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
import { toApiError, toFieldErrors } from '@/lib/api-client';
import type { AcademicYear } from '@erp/api-types';

import { useCreateAcademicYear, useUpdateAcademicYear } from '../api/use-academic';

function makeSchema(t: (key: string) => string) {
  return z
    .object({
      name: z.string().min(1, t('required')).max(64),
      start_date: z.string().min(1, t('required')),
      end_date: z.string().min(1, t('required')),
      is_current: z.boolean(),
    })
    // Mirrors the server-side CheckConstraint, so the user gets the error before
    // a round trip. The database remains the authority.
    .refine((values) => values.end_date > values.start_date, {
      path: ['end_date'],
      message: t('endAfterStart'),
    });
}

type FormValues = z.infer<ReturnType<typeof makeSchema>>;

interface AcademicYearFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  academicYear?: AcademicYear | null;
}

export function AcademicYearFormDialog({
  open,
  onOpenChange,
  academicYear = null,
}: AcademicYearFormDialogProps) {
  const t = useTranslations('academic');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const createMutation = useCreateAcademicYear();
  const updateMutation = useUpdateAcademicYear();

  const form = useForm<FormValues>({
    resolver: zodResolver(makeSchema(tv)),
    defaultValues: { name: '', start_date: '', end_date: '', is_current: false },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: academicYear?.name ?? '',
      start_date: academicYear?.start_date ?? '',
      end_date: academicYear?.end_date ?? '',
      is_current: academicYear?.is_current ?? false,
    });
  }, [open, academicYear, form]);

  async function onSubmit(values: FormValues) {
    try {
      if (academicYear) {
        await updateMutation.mutateAsync({ id: academicYear.id, payload: values });
        toast.success(t('yearUpdated'));
      } else {
        await createMutation.mutateAsync(values);
        toast.success(t('yearCreated'));
      }
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in values) {
          form.setError(field as keyof FormValues, { message });
          matched = true;
        }
      }
      if (!matched) toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  const errors = form.formState.errors;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={tc('close')}>
        <DialogHeader>
          <DialogTitle>{academicYear ? t('editYear') : t('newYear')}</DialogTitle>
          <DialogDescription>{t('yearFormHint')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField
            id="name"
            label={t('yearName')}
            error={errors.name?.message}
            hint={t('yearNameHint')}
            required
          >
            <Input
              id="name"
              placeholder="2026-2027"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={describedBy('name', errors.name?.message, t('yearNameHint'))}
              {...form.register('name')}
            />
          </FormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="start_date"
              label={t('startDate')}
              error={errors.start_date?.message}
              required
            >
              <Input
                id="start_date"
                type="date"
                aria-invalid={Boolean(errors.start_date)}
                aria-describedby={describedBy('start_date', errors.start_date?.message)}
                {...form.register('start_date')}
              />
            </FormField>

            <FormField
              id="end_date"
              label={t('endDate')}
              error={errors.end_date?.message}
              required
            >
              <Input
                id="end_date"
                type="date"
                aria-invalid={Boolean(errors.end_date)}
                aria-describedby={describedBy('end_date', errors.end_date?.message)}
                {...form.register('end_date')}
              />
            </FormField>
          </div>

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-[var(--primary)]"
              {...form.register('is_current')}
            />
            <span>
              {t('isCurrent')}
              <span className="block text-xs text-muted-foreground">
                {t('isCurrentHint')}
              </span>
            </span>
          </label>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
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
