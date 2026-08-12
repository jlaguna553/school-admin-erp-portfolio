'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';

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
import { MODULE_REQUIRES, OPTIONAL_MODULES } from '@/lib/access';
import { toApiError, toFieldErrors } from '@/lib/api-client';
import type { Institution } from '@erp/api-types';

import { useCreateInstitution, useUpdateInstitution } from '../api/use-platform';
import { makeInstitutionSchema, type InstitutionFormValues } from '../types/schemas';

interface InstitutionFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  institution?: Institution | null;
}

export function InstitutionFormDialog({
  open,
  onOpenChange,
  institution = null,
}: InstitutionFormDialogProps) {
  const t = useTranslations('platform');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');
  const tm = useTranslations('modules');

  const createMutation = useCreateInstitution();
  const updateMutation = useUpdateInstitution();

  const form = useForm<InstitutionFormValues>({
    resolver: zodResolver(makeInstitutionSchema(tv)),
    defaultValues: {
      name: '',
      legal_name: '',
      tax_id: '',
      default_language: 'es',
      default_currency: 'MXN',
      brand_color: '#1d4ed8',
      timezone: 'America/Mexico_City',
      disabled_modules: [],
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: institution?.name ?? '',
      legal_name: institution?.legal_name ?? '',
      tax_id: institution?.tax_id ?? '',
      default_language: (institution?.default_language as 'es' | 'en') ?? 'es',
      default_currency: (institution?.default_currency as 'MXN' | 'USD') ?? 'MXN',
      brand_color: institution?.brand_color ?? '#1d4ed8',
      timezone: institution?.timezone ?? 'America/Mexico_City',
      disabled_modules: institution?.disabled_modules ?? [],
    });
  }, [open, institution, form]);

  async function onSubmit(values: InstitutionFormValues) {
    try {
      if (institution) {
        await updateMutation.mutateAsync({ id: institution.id, payload: values });
        toast.success(t('institutionUpdated'));
      } else {
        await createMutation.mutateAsync(values);
        toast.success(t('institutionCreated'));
      }
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in values) {
          form.setError(field as keyof InstitutionFormValues, { message });
          matched = true;
        }
      }
      if (!matched) toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  const errors = form.formState.errors;
  const isProvisioning = !institution && form.formState.isSubmitting;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={tc('cancel')}>
        <DialogHeader>
          <DialogTitle>
            {institution ? t('editInstitution') : t('newInstitution')}
          </DialogTitle>
          <DialogDescription>
            {institution ? t('editInstitutionHint') : t('newInstitutionHint')}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField id="name" label={t('name')} error={errors.name?.message} required>
            <Input
              id="name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={describedBy('name', errors.name?.message)}
              {...form.register('name')}
            />
          </FormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="legal_name" label={t('legalName')} error={errors.legal_name?.message}>
              <Input id="legal_name" {...form.register('legal_name')} />
            </FormField>

            <FormField id="tax_id" label={t('taxId')} error={errors.tax_id?.message}>
              <Input id="tax_id" {...form.register('tax_id')} />
            </FormField>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <FormField id="default_language" label={t('language')}>
              <Select
                value={form.watch('default_language')}
                onValueChange={(value) =>
                  form.setValue('default_language', value as 'es' | 'en', { shouldDirty: true })
                }
              >
                <SelectTrigger id="default_language">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="es">Español</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                </SelectContent>
              </Select>
            </FormField>

            <FormField
              id="default_currency"
              label={t('currency')}
              hint={t('currencyHint')}
              error={errors.default_currency?.message}
            >
              <Select
                value={form.watch('default_currency')}
                onValueChange={(value) =>
                  form.setValue('default_currency', value as 'MXN' | 'USD', {
                    shouldDirty: true,
                  })
                }
              >
                <SelectTrigger id="default_currency">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="MXN">{t('currencies.MXN')}</SelectItem>
                  <SelectItem value="USD">{t('currencies.USD')}</SelectItem>
                </SelectContent>
              </Select>
            </FormField>

            <FormField id="timezone" label={t('timezone')} error={errors.timezone?.message}>
              <Input id="timezone" {...form.register('timezone')} />
            </FormField>
          </div>

          <FormField
            id="brand_color"
            label={t('brandColor')}
            hint={t('brandColorHint')}
            error={errors.brand_color?.message}
          >
            <div className="flex items-center gap-2">
              {/* Two controls over one value: the swatch for picking, the text
                  field for pasting the hex a brand guide actually specifies. */}
              <input
                type="color"
                aria-label={t('brandColorPicker')}
                className="size-9 shrink-0 cursor-pointer rounded-md border border-border bg-card p-1"
                value={form.watch('brand_color')}
                onChange={(event) =>
                  form.setValue('brand_color', event.target.value, { shouldDirty: true })
                }
              />
              <Input
                id="brand_color"
                className="font-mono"
                spellCheck={false}
                aria-invalid={Boolean(errors.brand_color)}
                aria-describedby={describedBy(
                  'brand_color',
                  errors.brand_color?.message,
                  t('brandColorHint'),
                )}
                {...form.register('brand_color')}
              />
            </div>
          </FormField>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">{t('modules')}</legend>
            <p className="text-xs text-muted-foreground">{t('modulesHint')}</p>

            <div className="grid gap-2 sm:grid-cols-2">
              {OPTIONAL_MODULES.map((module) => {
                const disabled = form.watch('disabled_modules');
                const off = disabled.includes(module);
                // A module whose prerequisite is off is off whatever this
                // checkbox says, so it is shown that way rather than ticked and
                // inert — and it names what switched it off.
                const requires = MODULE_REQUIRES[module];
                const blockedBy = requires && disabled.includes(requires) ? requires : null;

                return (
                  <label
                    key={module}
                    className={`flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm ${
                      blockedBy ? 'opacity-60' : ''
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="size-4 accent-[var(--primary)]"
                      checked={!off && !blockedBy}
                      disabled={Boolean(blockedBy)}
                      onChange={(event) => {
                        const current = form.getValues('disabled_modules');
                        form.setValue(
                          'disabled_modules',
                          event.target.checked
                            ? current.filter((key) => key !== module)
                            : [...current, module],
                          { shouldDirty: true },
                        );
                      }}
                    />
                    <span>
                      {tm(module)}
                      {blockedBy ? (
                        <span className="block text-xs text-muted-foreground">
                          {t('moduleRequires', { module: tm(blockedBy) })}
                        </span>
                      ) : null}
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

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
              {/* Provisioning creates a schema and runs its migrations, which
                  takes seconds -- say so rather than look frozen. */}
              {isProvisioning ? t('provisioning') : tc('save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
