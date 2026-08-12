import { test as base, expect, type Page } from '@playwright/test';

/**
 * Credentials for the demo school created by `create_school`.
 * Override via env when running against a different tenant.
 */
export const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'admin@northfield.test';
export const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'School!2026dev';

/**
 * The platform operator, who is above every school rather than a member of one.
 *
 * Created on boot from `PLATFORM_ADMIN_EMAIL` / `PLATFORM_ADMIN_PASSWORD`; the
 * dev stack sets both, so these defaults match a `docker compose up`.
 */
export const PLATFORM_EMAIL = process.env.E2E_PLATFORM_EMAIL ?? 'admin@platform.test';
export const PLATFORM_PASSWORD = process.env.E2E_PLATFORM_PASSWORD ?? 'Platform!2026dev';
/** Shown in the sidebar, read from the JWT's tenant claim. */
export const SCHOOL_NAME = process.env.E2E_SCHOOL_NAME ?? 'Northfield';

/** A value unique per run, so repeated runs never collide on unique fields. */
export function unique(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

/**
 * The page content area.
 *
 * Scope module assertions to this: the top bar repeats the page title and has
 * its own search box, so unscoped `getByRole` queries match two elements and
 * trip Playwright's strict mode.
 */
export function content(page: Page) {
  return page.locator('main');
}

export async function login(page: Page, locale = 'es'): Promise<void> {
  await page.goto(`/${locale}/login`);
  await page.fill('#email', ADMIN_EMAIL);
  await page.fill('#password', ADMIN_PASSWORD);
  await page.click('button[type=submit]');
  await page.waitForURL(new RegExp(`/${locale}/dashboard`), { timeout: 30_000 });
}

/**
 * Sign in as the platform operator.
 *
 * Lands on the console rather than a dashboard: an operator belongs to no
 * school, so there is no school dashboard to show them.
 */
export async function loginAsPlatform(page: Page, locale = 'es'): Promise<void> {
  await page.goto(`/${locale}/login`);
  await page.fill('#email', PLATFORM_EMAIL);
  await page.fill('#password', PLATFORM_PASSWORD);
  await page.click('button[type=submit]');
  await page.waitForURL(new RegExp(`/${locale}/platform`), { timeout: 30_000 });
}

/**
 * Test variant that fails on unexpected console errors.
 *
 * A React key warning or a failed request is a real defect; without this the
 * suite would pass while the console filled with errors.
 */
export const test = base.extend<{ consoleGuard: string[] }>({
  consoleGuard: async ({ page }, use) => {
    const errors: string[] = [];

    page.on('console', (message) => {
      if (message.type() !== 'error') return;
      const text = message.text();

      // Chromium logs every non-2xx response as a console error. Several tests
      // deliberately trigger 400s (wrong password, duplicate email) to check
      // that the API's field errors reach the form, so this would flag correct
      // behaviour as a failure. Genuine app faults still surface via
      // `pageerror` and through React's own console.error output.
      if (text.startsWith('Failed to load resource')) return;
      if (text.includes('favicon')) return;

      errors.push(text);
    });
    page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));

    await use(errors);

    expect(errors, `unexpected console errors:\n${errors.join('\n')}`).toEqual([]);
  },
});

export { expect };

/**
 * A signed-in page, ready at the dashboard.
 *
 * Each test logs in fresh. Reusing a saved `storageState` looks tempting but
 * cannot work here: refresh tokens rotate and the previous one is blacklisted,
 * so a saved cookie jar is good for exactly one restore and every later test
 * would be bounced to the login screen. That is the token rotation behaving
 * correctly, not a bug to design around.
 *
 * The consequence is a lot of logins, so the dev stack runs with relaxed
 * throttle limits (see docker-compose.yml); the production defaults stay strict
 * and are covered by the pytest suite instead.
 */
export const authedTest = test.extend<{ authedPage: Page }>({
  authedPage: async ({ page }, use) => {
    await login(page);
    await use(page);
  },
});
