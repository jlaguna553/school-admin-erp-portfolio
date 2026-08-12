'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import axios from 'axios';
import { GraduationCap, Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useForm } from 'react-hook-form';

import { LanguageSwitcher } from '@/components/layout/language-switcher';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toApiError, toFieldErrors } from '@/lib/api-client';

import { useLogin } from '../api/use-auth';
import { makeLoginSchema, type LoginFormValues } from '../types/schemas';

export function LoginForm() {
  const t = useTranslations('auth');
  const tv = useTranslations('validation');
  const login = useLogin();

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(makeLoginSchema(tv)),
    defaultValues: { email: '', password: '' },
  });

  async function onSubmit(values: LoginFormValues) {
    try {
      await login.mutateAsync(values);
    } catch (error) {
      // A 404 here does not mean "wrong password" -- it means this hostname is
      // not mapped to any institution, so the auth routes do not exist on it.
      // Without a specific message that surfaces as a baffling generic failure.
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        form.setError('root', { message: t('unknownInstitution') });
        return;
      }

      // Map the API's `details` map onto the matching inputs; anything without a
      // field lands in the form-level error below.
      const fieldErrors = toFieldErrors(error);
      let matched = false;
      for (const [field, message] of Object.entries(fieldErrors)) {
        if (field === 'email' || field === 'password') {
          form.setError(field, { message });
          matched = true;
        }
      }
      if (!matched) {
        form.setError('root', {
          message: toApiError(error)?.message ?? t('genericError'),
        });
      }
    }
  }

  const rootError = form.formState.errors.root?.message;

  return (
    <Card className="w-full max-w-sm p-6">
      <div className="mb-6 flex flex-col items-center gap-2 text-center">
        <div className="flex size-11 items-center justify-center rounded-xl bg-accent">
          <GraduationCap className="size-6 text-accent-foreground" aria-hidden />
        </div>
        <h1 className="text-xl font-bold tracking-tight">{t('signIn')}</h1>
        <p className="text-sm text-muted-foreground">{t('signInSubtitle')}</p>
      </div>

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="space-y-1.5">
          <Label htmlFor="email">{t('email')}</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={Boolean(form.formState.errors.email)}
            {...form.register('email')}
          />
          {form.formState.errors.email ? (
            <p className="text-xs text-destructive" role="alert">
              {form.formState.errors.email.message}
            </p>
          ) : null}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">{t('password')}</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={Boolean(form.formState.errors.password)}
            {...form.register('password')}
          />
          {form.formState.errors.password ? (
            <p className="text-xs text-destructive" role="alert">
              {form.formState.errors.password.message}
            </p>
          ) : null}
        </div>

        {rootError ? (
          <p
            className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive"
            role="alert"
          >
            {rootError}
          </p>
        ) : null}

        <Button type="submit" full disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : null}
          {t('signInAction')}
        </Button>
      </form>

      <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
        <p className="text-xs text-muted-foreground">{t('tenantHint')}</p>
        <LanguageSwitcher />
      </div>
    </Card>
  );
}
