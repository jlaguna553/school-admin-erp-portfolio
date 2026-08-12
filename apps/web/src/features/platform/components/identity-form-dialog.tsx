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
import { makeUserSchema, type UserFormValues } from '@/features/users/types/schemas';
import { toApiError, toFieldErrors } from '@/lib/api-client';
import type { PlatformIdentity } from '@erp/api-types';

import { useCreateIdentity, useUpdateIdentity } from '../api/use-identities';

interface IdentityFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  identity?: PlatformIdentity | null;
}

/**
 * A person, not an account at a school.
 *
 * Creating one grants access to nothing: schools are added afterwards, one
 * membership at a time. Keeping the two steps separate is what stops "create a
 * user" from quietly meaning "and give them the run of this school".
 */
export function IdentityFormDialog({
  open,
  onOpenChange,
  identity = null,
}: IdentityFormDialogProps) {
  const t = useTranslations('platform');
  const tu = useTranslations('users');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const mode = identity ? 'edit' : 'create';
  const createMutation = useCreateIdentity();
  const updateMutation = useUpdateIdentity();

  // Reuses the user schema minus the role: a role belongs to a membership, not
  // to the person -- the same person is an administrator at one school and a
  // teacher at another.
  const form = useForm<UserFormValues>({
    resolver: zodResolver(makeUserSchema(tv, mode)),
    defaultValues: {
      email: '',
      first_name: '',
      last_name: '',
      phone: '',
      role: 'school_admin',
      language: 'es',
      password: '',
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      email: identity?.email ?? '',
      first_name: identity?.first_name ?? '',
      last_name: identity?.last_name ?? '',
      phone: identity?.phone ?? '',
      role: 'school_admin',
      language: (identity?.language as 'es' | 'en') ?? 'es',
      password: '',
    });
  }, [open, identity, form]);

  async function onSubmit(values: UserFormValues) {
    const payload = {
      email: values.email,
      first_name: values.first_name,
      last_name: values.last_name,
      phone: values.phone,
      language: values.language,
    };
    try {
      if (identity) {
        await updateMutation.mutateAsync({ id: identity.id, payload });
        toast.success(t('personUpdated'));
      } else {
        await createMutation.mutateAsync({ ...payload, password: values.password });
        toast.success(t('personCreated'));
      }
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in values) {
          form.setError(field as keyof UserFormValues, { message });
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
          <DialogTitle>{identity ? t('editPerson') : t('newPerson')}</DialogTitle>
          <DialogDescription>{t('personHint')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="first_name"
              label={tu('firstName')}
              error={errors.first_name?.message}
              required
            >
              <Input
                id="first_name"
                aria-invalid={Boolean(errors.first_name)}
                aria-describedby={describedBy('first_name', errors.first_name?.message)}
                {...form.register('first_name')}
              />
            </FormField>

            <FormField
              id="last_name"
              label={tu('lastName')}
              error={errors.last_name?.message}
              required
            >
              <Input
                id="last_name"
                aria-invalid={Boolean(errors.last_name)}
                aria-describedby={describedBy('last_name', errors.last_name?.message)}
                {...form.register('last_name')}
              />
            </FormField>
          </div>

          <FormField id="email" label={tu('email')} error={errors.email?.message} required>
            <Input
              id="email"
              type="email"
              autoComplete="off"
              aria-invalid={Boolean(errors.email)}
              aria-describedby={describedBy('email', errors.email?.message)}
              {...form.register('email')}
            />
          </FormField>

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="phone" label={tu('phone')}>
              <Input id="phone" {...form.register('phone')} />
            </FormField>

            <FormField id="language" label={tu('language')}>
              <Select
                value={form.watch('language')}
                onValueChange={(value) =>
                  form.setValue('language', value as 'es' | 'en', { shouldDirty: true })
                }
              >
                <SelectTrigger id="language">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="es">Español</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                </SelectContent>
              </Select>
            </FormField>
          </div>

          {!identity ? (
            <FormField
              id="password"
              label={tu('password')}
              error={errors.password?.message}
              hint={t('onePasswordHint')}
              required
            >
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                aria-invalid={Boolean(errors.password)}
                aria-describedby={describedBy(
                  'password',
                  errors.password?.message,
                  t('onePasswordHint'),
                )}
                {...form.register('password')}
              />
            </FormField>
          ) : null}

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
