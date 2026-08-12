import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Link } from '@/i18n/navigation';

export default function LocaleNotFound() {
  const t = useTranslations('common');

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm px-6 py-10 text-center">
        <p className="tabular text-3xl font-bold text-muted-foreground">404</p>
        <h1 className="mt-2 text-lg font-semibold tracking-tight">{t('notFoundTitle')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t('notFoundBody')}</p>
        <Button asChild className="mt-5">
          <Link href="/dashboard">{t('backToDashboard')}</Link>
        </Button>
      </Card>
    </main>
  );
}
