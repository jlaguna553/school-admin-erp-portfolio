import { getTranslations, setRequestLocale } from 'next-intl/server';
import type { Metadata } from 'next';

import { AppShell } from '@/components/layout/app-shell';
import { SubjectsView } from '@/features/academic/components/subjects-view';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'nav' });
  return { title: t('subjects') };
}

export default async function SubjectsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <AppShell titleKey="subjects" requires="subjects">
      <SubjectsView />
    </AppShell>
  );
}
