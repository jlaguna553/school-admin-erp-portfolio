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
import type { User } from '@erp/api-types';

import {
  useAssignableRoles,
  useCreateInstitutionUser,
  useUpdateInstitutionUser,
} from '../api/use-platform';

interface InstitutionUserFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  institutionId: string;
  user?: User | null;
}

/**
 * Create or amend an account *inside* a school, from the platform host.
 *
 * Deliberately not the school's own `UserFormDialog`: that one posts to
 * `/api/v1/users/`, which on this host would write into the public schema and
 * silently create a platform account instead of a school one.
 */
export function InstitutionUserFormDialog({
  open,
  onOpenChange,
  institutionId,
  user = null,
}: InstitutionUserFormDialogProps) {
  const t = useTranslations('users');
  const tp = useTranslations('platform');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const mode = user ? 'edit' : 'create';
  const createMutation = useCreateInstitutionUser(institutionId);
  const updateMutation = useUpdateInstitutionUser(institutionId);
  const { data: roles = [] } = useAssignableRoles();

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
      email: user?.email ?? '',
      first_name: user?.first_name ?? '',
      last_name: user?.last_name ?? '',
      phone: user?.phone ?? '',
      role: user?.role ?? 'school_admin',
      language: (user?.language as 'es' | 'en') ?? 'es',
      password: '',
    });
  }, [open, user, form]);

  async function onSubmit(values: UserFormValues) {
    try {
      if (user) {
        // `password` is never sent on edit: there is no admin password-reset
        // endpoint, and only the account owner may change their own.
        const payload = {
          email: values.email,
          first_name: values.first_name,
          last_name: values.last_name,
          phone: values.phone,
          role: values.role,
          language: values.language,
        };
        await updateMutation.mutateAsync({ id: user.id, payload });
        toast.success(t('updated'));
      } else {
        await createMutation.mutateAsync(values);
        toast.success(t('created'));
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
          <DialogTitle>{user ? t('editTitle') : t('createTitle')}</DialogTitle>
          <DialogDescription>{tp('userDialogHint')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id="first_name"
              label={t('firstName')}
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
              label={t('lastName')}
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

          <FormField id="email" label={t('email')} error={errors.email?.message} required>
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
            <FormField id="role" label={t('role')} error={errors.role?.message} required>
              <Select
                value={form.watch('role')}
                onValueChange={(value) => form.setValue('role', value, { shouldDirty: true })}
              >
                <SelectTrigger id="role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roles.map((role) => (
                    <SelectItem key={role.value} value={role.value}>
                      {role.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>

            <FormField id="language" label={t('language')}>
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

          {!user ? (
            <FormField
              id="password"
              label={t('password')}
              error={errors.password?.message}
              hint={t('passwordHint')}
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
                  t('passwordHint'),
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
