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
import { useAllAcademicYears } from '@/features/academic/api/use-academic';
import { toApiError, toFieldErrors } from '@/lib/api-client';
import type { Term } from '@erp/api-types';

import { useCreateTerm, useUpdateTerm } from '../api/use-grades';

function makeTermSchema(t: (key: string) => string) {
  return z
    .object({
      academic_year: z.string().min(1, t('required')),
      name: z.string().min(1, t('required')).max(64),
      ordinal: z.coerce.number().int().min(1),
      start_date: z.string().min(1, t('required')),
      end_date: z.string().min(1, t('required')),
      is_current: z.boolean(),
    })
    .refine((value) => value.end_date >= value.start_date, {
      path: ['end_date'],
      message: t('endAfterStart'),
    });
}

type TermFormValues = z.infer<ReturnType<typeof makeTermSchema>>;

interface TermFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  term?: Term | null;
}

/**
 * Open or amend an evaluation period.
 *
 * Without this the gradebook has nothing to hang marks on: a school with no
 * periods shows an empty subject selector and no way forward, which is exactly
 * the state a freshly provisioned institution starts in.
 */
export function TermFormDialog({ open, onOpenChange, term = null }: TermFormDialogProps) {
  const t = useTranslations('grades');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const { data: years = [] } = useAllAcademicYears();
  const createMutation = useCreateTerm();
  const updateMutation = useUpdateTerm();

  const form = useForm<TermFormValues>({
    resolver: zodResolver(makeTermSchema(tv)),
    defaultValues: {
      academic_year: '',
      name: '',
      ordinal: 1,
      start_date: '',
      end_date: '',
      is_current: false,
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      academic_year:
        term?.academic_year ?? (years.find((y) => y.is_current) ?? years[0])?.id ?? '',
      name: term?.name ?? '',
      ordinal: term?.ordinal ?? 1,
      start_date: term?.start_date ?? '',
      end_date: term?.end_date ?? '',
      is_current: term?.is_current ?? false,
    });
  }, [open, term, years, form]);

  async function onSubmit(values: TermFormValues) {
    try {
      if (term) {
        await updateMutation.mutateAsync({ id: term.id, payload: values });
        toast.success(t('termUpdated'));
      } else {
        await createMutation.mutateAsync(values);
        toast.success(t('termCreated'));
      }
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in values) {
          form.setError(field as keyof TermFormValues, { message });
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
          <DialogTitle>{term ? t('editTerm') : t('newTerm')}</DialogTitle>
          <DialogDescription>{t('termHint')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField id="term_name" label={t('termName')} error={errors.name?.message} required>
            <Input
              id="term_name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={describedBy('term_name', errors.name?.message)}
              {...form.register('name')}
            />
          </FormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="academic_year" label={t('academicYear')} required>
              <Select
                value={form.watch('academic_year')}
                onValueChange={(value) =>
                  form.setValue('academic_year', value, { shouldDirty: true })
                }
              >
                <SelectTrigger id="academic_year">
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

            <FormField
              id="ordinal"
              label={t('ordinal')}
              hint={t('ordinalHint')}
              error={errors.ordinal?.message}
            >
              <Input id="ordinal" type="number" min={1} {...form.register('ordinal')} />
            </FormField>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="start_date"
              label={t('startDate')}
              error={errors.start_date?.message}
              required
            >
              <Input id="start_date" type="date" {...form.register('start_date')} />
            </FormField>

            <FormField
              id="end_date"
              label={t('endDate')}
              error={errors.end_date?.message}
              required
            >
              <Input id="end_date" type="date" {...form.register('end_date')} />
            </FormField>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-[var(--primary)]"
              checked={form.watch('is_current')}
              onChange={(event) =>
                form.setValue('is_current', event.target.checked, { shouldDirty: true })
              }
            />
            {t('isCurrent')}
          </label>

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
