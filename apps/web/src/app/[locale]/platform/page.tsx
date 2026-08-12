import { getTranslations, setRequestLocale } from 'next-intl/server';
import type { Metadata } from 'next';

import { AppShell } from '@/components/layout/app-shell';
import { InstitutionsView } from '@/features/platform/components/institutions-view';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'nav' });
  return { title: t('institutions') };
}

/**
 * The operator console. Only reachable on the platform host — on a school's
 * hostname the API behind it returns 404, so the page renders an empty table.
 */
export default async function PlatformPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <AppShell titleKey="institutions" nav="platform" requires="platform">
      <InstitutionsView />
    </AppShell>
  );
}
