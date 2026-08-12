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

import {
  useCreateProgram,
  useProgramTranslations,
  useUpdateProgram,
} from '../api/use-academic';

/**
 * Programme editor.
 *
 * Spanish is the project's default language and `required_languages = ("es",)`
 * on the model, so `name_es` is mandatory while `name_en` may be left blank —
 * reads then fall back to Spanish.
 */
function makeSchema(t: (key: string) => string) {
  return z.object({
    code: z.string().min(1, t('required')).max(32),
    name_es: z.string().min(1, t('required')).max(200),
    name_en: z.string().max(200).optional().or(z.literal('')),
    description_es: z.string().optional().or(z.literal('')),
    description_en: z.string().optional().or(z.literal('')),
  });
}

type FormValues = z.infer<ReturnType<typeof makeSchema>>;

interface ProgramFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  programId?: string | null;
}

export function ProgramFormDialog({
  open,
  onOpenChange,
  programId = null,
}: ProgramFormDialogProps) {
  const t = useTranslations('academic');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const createMutation = useCreateProgram();
  const updateMutation = useUpdateProgram();
  // Editing needs the raw per-language columns, not the resolved `name`.
  const { data: existing } = useProgramTranslations(open ? programId : null);

  const form = useForm<FormValues>({
    resolver: zodResolver(makeSchema(tv)),
    defaultValues: {
      code: '',
      name_es: '',
      name_en: '',
      description_es: '',
      description_en: '',
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      code: existing?.code ?? '',
      name_es: existing?.name_es ?? '',
      name_en: existing?.name_en ?? '',
      description_es: existing?.description_es ?? '',
      description_en: existing?.description_en ?? '',
    });
  }, [open, existing, form]);

  async function onSubmit(values: FormValues) {
    const payload = {
      code: values.code,
      name_es: values.name_es,
      name_en: values.name_en ?? '',
      description_es: values.description_es ?? '',
      description_en: values.description_en ?? '',
    };

    try {
      if (programId) {
        await updateMutation.mutateAsync({ id: programId, payload });
        toast.success(t('programUpdated'));
      } else {
        await createMutation.mutateAsync(payload);
        toast.success(t('programCreated'));
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
          <DialogTitle>
            {programId ? t('editProgram') : t('newProgram')}
          </DialogTitle>
          <DialogDescription>{t('programFormHint')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField
            id="code"
            label={t('code')}
            error={errors.code?.message}
            hint={t('codeHint')}
            required
          >
            <Input
              id="code"
              aria-invalid={Boolean(errors.code)}
              aria-describedby={describedBy('code', errors.code?.message, t('codeHint'))}
              {...form.register('code')}
            />
          </FormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="name_es"
              label={`${t('name')} (ES)`}
              error={errors.name_es?.message}
              required
            >
              <Input
                id="name_es"
                aria-invalid={Boolean(errors.name_es)}
                aria-describedby={describedBy('name_es', errors.name_es?.message)}
                {...form.register('name_es')}
              />
            </FormField>

            <FormField
              id="name_en"
              label={`${t('name')} (EN)`}
              error={errors.name_en?.message}
              hint={t('fallbackHint')}
            >
              <Input
                id="name_en"
                aria-describedby={describedBy(
                  'name_en',
                  errors.name_en?.message,
                  t('fallbackHint'),
                )}
                {...form.register('name_en')}
              />
            </FormField>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="description_es" label={`${t('description')} (ES)`}>
              <Input id="description_es" {...form.register('description_es')} />
            </FormField>
            <FormField id="description_en" label={`${t('description')} (EN)`}>
              <Input id="description_en" {...form.register('description_en')} />
            </FormField>
          </div>

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
