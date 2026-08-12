'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import { PageHeader } from '@/components/layout/page-header';
import { Button } from '@/components/ui/button';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { FormField, describedBy } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { authKeys, useSession } from '@/features/auth/api/use-auth';
import { usePathname, useRouter } from '@/i18n/navigation';
import { apiClient, toApiError, toFieldErrors } from '@/lib/api-client';
import { decodeAccessToken, getAccessToken } from '@/lib/auth/token-store';

export function SettingsView() {
  const t = useTranslations('settings');
  const { user, isPending } = useSession();

  if (isPending || !user) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-9 w-56" />
        <Skeleton className="h-64 w-full max-w-2xl" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-5">
      <PageHeader title={t('title')} description={t('subtitle')} />
      <InstitutionCard />
      <ProfileCard />
      <PasswordCard />
    </div>
  );
}

/** Read-only: the institution comes from the JWT's tenant claims. */
function InstitutionCard() {
  const t = useTranslations('settings');
  const claims = decodeAccessToken(getAccessToken());

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t('institution')}</CardTitle>
          <CardDescription>{t('institutionHint')}</CardDescription>
        </div>
      </CardHeader>
      <dl className="grid gap-3 px-5 pb-5 pt-2 sm:grid-cols-2">
        <div>
          <dt className="text-xs text-muted-foreground">{t('institutionName')}</dt>
          <dd className="text-sm font-medium">{claims?.tenant_name ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{t('schema')}</dt>
          <dd className="font-mono text-sm">{claims?.tenant_schema ?? '—'}</dd>
        </div>
      </dl>
    </Card>
  );
}

function makeProfileSchema(t: (key: string) => string) {
  return z.object({
    first_name: z.string().min(1, t('required')).max(150),
    last_name: z.string().min(1, t('required')).max(150),
    phone: z.string().max(32).optional().or(z.literal('')),
    language: z.enum(['es', 'en']),
  });
}

function ProfileCard() {
  const t = useTranslations('settings');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const { user } = useSession();
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();

  const schema = makeProfileSchema(tv);
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { first_name: '', last_name: '', phone: '', language: 'es' },
  });

  useEffect(() => {
    if (!user) return;
    form.reset({
      first_name: user.first_name ?? '',
      last_name: user.last_name ?? '',
      phone: user.phone ?? '',
      language: (user.language as 'es' | 'en') ?? 'es',
    });
  }, [user, form]);

  async function onSubmit(values: z.infer<typeof schema>) {
    try {
      await apiClient.patch('/api/v1/users/me/', values);
      await queryClient.invalidateQueries({ queryKey: authKeys.me });
      toast.success(t('profileSaved'));

      // The saved preference is the fallback for clients that send no
      // Accept-Language header; move the UI to match so the two agree.
      if (values.language !== locale) {
        router.replace(pathname, { locale: values.language });
      }
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field in values) {
          form.setError(field as keyof z.infer<typeof schema>, { message });
          matched = true;
        }
      }
      if (!matched) toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  const errors = form.formState.errors;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t('profile')}</CardTitle>
          <CardDescription>{t('profileHint')}</CardDescription>
        </div>
      </CardHeader>

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 px-5 pb-5 pt-2" noValidate>
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

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField id="settings-email" label={t('email')} hint={t('emailHint')}>
            {/* Email is the login identifier and is read-only server-side. */}
            <Input id="settings-email" value={user?.email ?? ''} readOnly disabled />
          </FormField>
          <FormField id="settings-phone" label={t('phone')} error={errors.phone?.message}>
            <Input id="settings-phone" {...form.register('phone')} />
          </FormField>
        </div>

        <FormField id="settings-language" label={t('language')} hint={t('languageHint')}>
          <Select
            value={form.watch('language')}
            onValueChange={(value) =>
              form.setValue('language', value as 'es' | 'en', { shouldDirty: true })
            }
          >
            <SelectTrigger id="settings-language">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="es">Español</SelectItem>
              <SelectItem value="en">English</SelectItem>
            </SelectContent>
          </Select>
        </FormField>

        <div className="flex justify-end">
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : null}
            {tc('save')}
          </Button>
        </div>
      </form>
    </Card>
  );
}

function makePasswordSchema(t: (key: string) => string) {
  return z
    .object({
      current_password: z.string().min(1, t('required')),
      new_password: z.string().min(8, t('passwordTooShort')),
      confirm_password: z.string().min(1, t('required')),
    })
    .refine((values) => values.new_password === values.confirm_password, {
      path: ['confirm_password'],
      message: t('passwordsDoNotMatch'),
    });
}

function PasswordCard() {
  const t = useTranslations('settings');
  const tc = useTranslations('common');
  const tv = useTranslations('validation');

  const schema = makePasswordSchema(tv);
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  });

  async function onSubmit(values: z.infer<typeof schema>) {
    try {
      await apiClient.post('/api/v1/users/me/change-password/', {
        current_password: values.current_password,
        new_password: values.new_password,
      });
      toast.success(t('passwordChanged'));
      form.reset();
    } catch (error) {
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field === 'current_password' || field === 'new_password') {
          form.setError(field, { message });
          matched = true;
        }
      }
      if (!matched) toast.error(toApiError(error)?.message ?? tc('genericError'));
    }
  }

  const errors = form.formState.errors;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t('password')}</CardTitle>
          <CardDescription>{t('passwordHint')}</CardDescription>
        </div>
      </CardHeader>

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 px-5 pb-5 pt-2" noValidate>
        <FormField
          id="current_password"
          label={t('currentPassword')}
          error={errors.current_password?.message}
          required
        >
          <Input
            id="current_password"
            type="password"
            autoComplete="current-password"
            aria-invalid={Boolean(errors.current_password)}
            aria-describedby={describedBy('current_password', errors.current_password?.message)}
            {...form.register('current_password')}
          />
        </FormField>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            id="new_password"
            label={t('newPassword')}
            error={errors.new_password?.message}
            required
          >
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.new_password)}
              aria-describedby={describedBy('new_password', errors.new_password?.message)}
              {...form.register('new_password')}
            />
          </FormField>

          <FormField
            id="confirm_password"
            label={t('confirmPassword')}
            error={errors.confirm_password?.message}
            required
          >
            <Input
              id="confirm_password"
              type="password"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.confirm_password)}
              aria-describedby={describedBy('confirm_password', errors.confirm_password?.message)}
              {...form.register('confirm_password')}
            />
          </FormField>
        </div>

        <div className="flex justify-end">
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : null}
            {t('changePassword')}
          </Button>
        </div>
      </form>
    </Card>
  );
}
