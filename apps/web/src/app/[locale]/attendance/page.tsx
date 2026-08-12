import { getTranslations, setRequestLocale } from 'next-intl/server';
import type { Metadata } from 'next';

import { AppShell } from '@/components/layout/app-shell';
import { AttendanceView } from '@/features/schedule/components/attendance-view';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'nav' });
  return { title: t('attendance') };
}

export default async function AttendancePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <AppShell titleKey="attendance" requires="attendance">
      <AttendanceView />
    </AppShell>
  );
}
