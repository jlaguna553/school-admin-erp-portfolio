'use client';

import { useEffect } from 'react';

import { brandStylesheet } from '@/lib/brand';
import { decodeAccessToken, getAccessToken, subscribe } from '@/lib/auth/token-store';

const STYLE_ID = 'school-brand';

/**
 * Paint the interface in the current school's colour.
 *
 * This used to be resolved on the server from the request host and inlined into
 * the page, which meant no repaint. One domain took that away: nothing about a
 * request says which school is being visited until the session does, so the
 * colour now arrives in the access token and is applied here.
 *
 * The consequence is visible and worth naming: the login page wears the
 * platform's colour, and the school's is applied a moment after signing in.
 * Reading it from the token rather than fetching it keeps that moment as short
 * as possible — a reload restores the session from the refresh cookie and the
 * colour is already in the new token, with no extra round trip.
 */
export function BrandTheme() {
  useEffect(() => {
    function apply() {
      const claims = decodeAccessToken(getAccessToken());
      const element = document.getElementById(STYLE_ID);

      if (!claims?.brand_color) {
        // Signed out, or a platform operator: fall back to the stylesheet's
        // own tokens rather than keeping the last school's colour on screen.
        element?.remove();
        return;
      }

      const style = element ?? document.createElement('style');
      style.id = STYLE_ID;
      style.textContent = brandStylesheet(claims.brand_color);
      if (!element) document.head.append(style);
    }

    apply();
    // Fires on sign-in, sign-out, refresh and school switch alike.
    return subscribe(apply);
  }, []);

  return null;
}
