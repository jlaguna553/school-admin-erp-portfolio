import { getTranslations, setRequestLocale } from 'next-intl/server';
import type { Metadata } from 'next';

import { LoginForm } from '@/features/auth/components/login-form';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'auth' });
  return { title: t('signIn') };
}

export default async function LoginPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-4">
      <LoginForm />
    </main>
  );
}
