import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages, setRequestLocale } from 'next-intl/server';
import { notFound } from 'next/navigation';

import { Providers } from '@/components/providers';
import { routing } from '@/i18n/routing';
import { BrandTheme } from '@/components/layout/brand-theme';

import '../globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'ERP Escolar',
    template: '%s · ERP Escolar',
  },
  description: 'Multi-institution school administration ERP.',
};

/** Pre-renders both locale trees at build time. */
export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!routing.locales.includes(locale as never)) {
    notFound();
  }

  // Opts this tree into static rendering for the given locale. Possible again
  // now that nothing in the layout depends on the request host: one domain
  // serves every school, and the school's colour is applied client-side from
  // the session.
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className={`${inter.variable} font-sans`}>
        <NextIntlClientProvider messages={messages}>
          <Providers locale={locale}>
            <BrandTheme />
            {children}
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
