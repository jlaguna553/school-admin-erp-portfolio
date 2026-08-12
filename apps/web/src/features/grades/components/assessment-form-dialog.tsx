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

import { useCreateAssessment } from '../api/use-grades';

function makeAssessmentSchema(t: (key: string) => string) {
  const decimal = z.string().regex(/^\d+(\.\d{1,2})?$/, t('invalidNumber'));
  return z.object({
    name: z.string().min(1, t('required')).max(200),
    // Kept as strings all the way to the API: parsing marks into JavaScript
    // numbers would round them in the browser, and a mark is a claim about a
    // person's work.
    max_score: decimal,
    weight: decimal,
    due_date: z.string().optional().or(z.literal('')),
  });
}

type AssessmentFormValues = z.infer<ReturnType<typeof makeAssessmentSchema>>;

interface AssessmentFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subjectId: string;
  termId: string;
}

export function AssessmentFormDialog({
  open,
  onOpenChange,
  subjectId,
  termId,
}: AssessmentFormDialogProps) {
  const t = useTranslations('grades');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const create = useCreateAssessment();

  const form = useForm<AssessmentFormValues>({
    resolver: zodResolver(makeAssessmentSchema(tv)),
    defaultValues: { name: '', max_score: '10.00', weight: '1.00', due_date: '' },
  });

  useEffect(() => {
    if (open) form.reset({ name: '', max_score: '10.00', weight: '1.00', due_date: '' });
  }, [open, form]);

  async function onSubmit(values: AssessmentFormValues) {
    try {
      await create.mutateAsync({
        subject: subjectId,
        term: termId,
        name: values.name,
        max_score: values.max_score,
        weight: values.weight,
        ...(values.due_date ? { due_date: values.due_date } : {}),
      });
      toast.success(t('assessmentCreated'));
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in values) {
          form.setError(field as keyof AssessmentFormValues, { message });
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
          <DialogTitle>{t('newAssessment')}</DialogTitle>
          <DialogDescription>{t('newAssessmentHint')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField id="name" label={t('assessmentName')} error={errors.name?.message} required>
            <Input
              id="name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={describedBy('name', errors.name?.message)}
              {...form.register('name')}
            />
          </FormField>

          <div className="grid gap-4 sm:grid-cols-3">
            <FormField
              id="max_score"
              label={t('maxScore')}
              hint={t('maxScoreHint')}
              error={errors.max_score?.message}
              required
            >
              <Input id="max_score" inputMode="decimal" {...form.register('max_score')} />
            </FormField>

            <FormField
              id="weight"
              label={t('weight')}
              hint={t('weightHint')}
              error={errors.weight?.message}
              required
            >
              <Input id="weight" inputMode="decimal" {...form.register('weight')} />
            </FormField>

            <FormField id="due_date" label={t('dueDate')} error={errors.due_date?.message}>
              <Input id="due_date" type="date" {...form.register('due_date')} />
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
