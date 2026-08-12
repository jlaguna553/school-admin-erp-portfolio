'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, useTheme } from 'next-themes';
import { Toaster } from 'sonner';
import { useEffect, useState, type ReactNode } from 'react';

import { setApiLocale } from '@/lib/api-client';
import { getQueryClient } from '@/lib/query-client';

interface ProvidersProps {
  children: ReactNode;
  locale: string;
}

export function Providers({ children, locale }: ProvidersProps) {
  // `useState` (not a module constant) so each browser session gets one client
  // and React's strict-mode double render does not create two.
  const [queryClient] = useState(getQueryClient);

  // Keep the Axios `Accept-Language` header in step with the URL locale, so a
  // language switch immediately changes the language of API error messages too.
  useEffect(() => {
    setApiLocale(locale);
  }, [locale]);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        {children}
        <ThemedToaster />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

/**
 * Toasts follow the app theme.
 *
 * `next-themes` resolves the theme on the client only, so this has to live
 * inside `ThemeProvider` rather than being configured statically.
 */
function ThemedToaster() {
  const { resolvedTheme } = useTheme();

  return (
    <Toaster
      position="bottom-right"
      richColors
      closeButton
      theme={resolvedTheme === 'dark' ? 'dark' : 'light'}
      toastOptions={{ duration: 4000 }}
    />
  );
}
