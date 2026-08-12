'use client';

import { useEffect, useState } from 'react';

import { decodeAccessToken, getAccessToken, subscribe } from '@/lib/auth/token-store';
import type { Currency } from '@erp/api-types';

/**
 * The institution's billing currency, for formatting amounts.
 *
 * Read from the access token rather than fetched, because a reload restores the
 * session through the refresh endpoint, which returns only an access token --
 * there is no `tenant` payload to read it from, and an extra request would
 * leave every amount briefly formatted in the wrong currency.
 *
 * Display only. The server denominates the invoice; this never decides it.
 */
export function useTenantCurrency(): Currency {
  const [currency, setCurrency] = useState<Currency>(() => readCurrency());

  useEffect(() => {
    setCurrency(readCurrency());
    return subscribe(() => setCurrency(readCurrency()));
  }, []);

  return currency;
}

function readCurrency(): Currency {
  const claims = decodeAccessToken(getAccessToken());
  // MXN matches the server's own default for a school that has never been
  // configured, so the two cannot disagree.
  return claims?.tenant_currency ?? 'MXN';
}
