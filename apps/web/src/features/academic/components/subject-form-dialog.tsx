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
import { useUsers } from '@/features/users/api/use-users';
import { toApiError, toFieldErrors } from '@/lib/api-client';
import type { Subject } from '@erp/api-types';

import { useCreateSubject, useProgramOptions, useUpdateSubject } from '../api/use-academic';

const NO_TEACHER = '__none__';

function makeSchema(t: (key: string) => string) {
  return z.object({
    code: z.string().min(1, t('required')).max(32),
    name: z.string().min(1, t('required')).max(200),
    credits: z.coerce
      .number({ invalid_type_error: t('invalidNumber') })
      .int()
      .min(1, t('positiveNumber'))
      .max(100),
    program: z.string().min(1, t('required')),
    teacher: z.string().optional(),
  });
}

type FormValues = z.input<ReturnType<typeof makeSchema>>;
type ParsedValues = z.output<ReturnType<typeof makeSchema>>;

interface SubjectFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subject?: Subject | null;
}

export function SubjectFormDialog({
  open,
  onOpenChange,
  subject = null,
}: SubjectFormDialogProps) {
  const t = useTranslations('subjects');
  const ta = useTranslations('academic');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const createMutation = useCreateSubject();
  const updateMutation = useUpdateSubject();
  const { data: programs = [] } = useProgramOptions();
  // Only teachers can be assigned, so the selector is filtered server-side.
  const { data: teachers } = useUsers({ role: 'teacher', page_size: 200, ordering: 'last_name' });

  const form = useForm<FormValues, unknown, ParsedValues>({
    resolver: zodResolver(makeSchema(tv)),
    defaultValues: { code: '', name: '', credits: 1, program: '', teacher: NO_TEACHER },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      code: subject?.code ?? '',
      name: subject?.name ?? '',
      credits: subject?.credits ?? 1,
      program: subject?.program ?? '',
      teacher: subject?.teacher ?? NO_TEACHER,
    });
  }, [open, subject, form]);

  async function onSubmit(values: ParsedValues) {
    const payload = {
      code: values.code,
      name: values.name,
      credits: values.credits,
      program: values.program,
      // The sentinel exists because Radix Select cannot hold an empty string.
      teacher: values.teacher === NO_TEACHER ? null : (values.teacher ?? null),
    };

    try {
      if (subject) {
        await updateMutation.mutateAsync({ id: subject.id, payload });
        toast.success(t('updated'));
      } else {
        await createMutation.mutateAsync(payload);
        toast.success(t('created'));
      }
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in payload) {
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
          <DialogTitle>{subject ? t('editTitle') : t('createTitle')}</DialogTitle>
          <DialogDescription>{t('formHint')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-[1fr_2fr]">
            <FormField id="code" label={ta('code')} error={errors.code?.message} required>
              <Input
                id="code"
                aria-invalid={Boolean(errors.code)}
                aria-describedby={describedBy('code', errors.code?.message)}
                {...form.register('code')}
              />
            </FormField>

            <FormField id="name" label={ta('name')} error={errors.name?.message} required>
              <Input
                id="name"
                aria-invalid={Boolean(errors.name)}
                aria-describedby={describedBy('name', errors.name?.message)}
                {...form.register('name')}
              />
            </FormField>
          </div>

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
                      {program.code} — {program.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>

            <FormField id="credits" label={t('credits')} error={errors.credits?.message} required>
              <Input
                id="credits"
                type="number"
                min={1}
                max={100}
                aria-invalid={Boolean(errors.credits)}
                aria-describedby={describedBy('credits', errors.credits?.message)}
                {...form.register('credits')}
              />
            </FormField>
          </div>

          <FormField id="teacher" label={t('teacher')} error={errors.teacher?.message}>
            <Select
              value={form.watch('teacher') || NO_TEACHER}
              onValueChange={(value) => form.setValue('teacher', value, { shouldDirty: true })}
            >
              <SelectTrigger id="teacher">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_TEACHER}>{t('unassigned')}</SelectItem>
                {(teachers?.results ?? []).map((teacher) => (
                  <SelectItem key={teacher.id} value={teacher.id}>
                    {teacher.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

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
