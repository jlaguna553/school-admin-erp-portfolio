import { redirect } from '@/i18n/navigation';

/**
 * The locale root has no content of its own — send people to the dashboard.
 * `AppShell` bounces unauthenticated visitors on to `/login` from there, so the
 * decision lives in exactly one place.
 */
export default async function LocaleIndexPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  redirect({ href: '/dashboard', locale });
}
