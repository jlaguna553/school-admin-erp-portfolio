import { getTranslations, setRequestLocale } from 'next-intl/server';
import type { Metadata } from 'next';

import { AppShell } from '@/components/layout/app-shell';
import { InstitutionUsersView } from '@/features/platform/components/institution-users-view';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'platform' });
  return { title: t('institutionUsersTitle') };
}

export default async function InstitutionUsersPage({
  params,
}: {
  params: Promise<{ locale: string; institutionId: string }>;
}) {
  const { locale, institutionId } = await params;
  setRequestLocale(locale);

  return (
    <AppShell titleKey="institutions" nav="platform" requires="platform">
      <InstitutionUsersView institutionId={institutionId} />
    </AppShell>
  );
}
