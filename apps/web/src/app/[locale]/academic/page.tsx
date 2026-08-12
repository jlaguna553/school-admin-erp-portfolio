import { getTranslations, setRequestLocale } from 'next-intl/server';
import type { Metadata } from 'next';

import { AppShell } from '@/components/layout/app-shell';
import { AcademicView } from '@/features/academic/components/academic-view';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'nav' });
  return { title: t('academic') };
}

export default async function AcademicPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <AppShell titleKey="academic" requires="academic">
      <AcademicView />
    </AppShell>
  );
}
