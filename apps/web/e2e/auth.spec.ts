import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  SCHOOL_NAME,
  content,
  expect,
  login,
  test,
} from './fixtures';

test.describe('Authentication', () => {
  test('rejects bad credentials without navigating', async ({ page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/login');
    await page.fill('#email', ADMIN_EMAIL);
    await page.fill('#password', 'definitely-not-the-password');
    await page.click('button[type=submit]');

    // The error comes from the API in the request's language.
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test('signs in and lands on the dashboard', async ({ page, consoleGuard }) => {
    void consoleGuard;
    await login(page);

    await expect(page).toHaveURL(/\/es\/dashboard/);
    // Sidebar renders the institution name from the JWT tenant claim.
    await expect(page.locator('aside')).toContainText(SCHOOL_NAME);
  });

  test('an unauthenticated visitor is redirected to login', async ({ page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/students');
    await expect(page).toHaveURL(/\/login/, { timeout: 20_000 });
  });

  test('the session survives a language switch', async ({ page, consoleGuard }) => {
    void consoleGuard;
    await login(page);

    await page.getByRole('button', { name: 'en', exact: true }).click();
    await page.waitForURL(/\/en\/dashboard/);

    // Still authenticated, and the UI is now in English.
    await expect(page.locator('aside')).toBeVisible();
    await expect(content(page).getByRole('heading', { level: 2 }).first()).toContainText(
      'Welcome back',
    );
  });

  test('the session survives a reload', async ({ page, consoleGuard }) => {
    void consoleGuard;
    await login(page);

    // The access token is memory-only, so this exercises the refresh-token
    // exchange on boot rather than a cached credential.
    await page.reload();
    await expect(page).toHaveURL(/\/es\/dashboard/);
    await expect(page.locator('aside')).toBeVisible();
  });

  test('no token is reachable from JavaScript', async ({ page, context, consoleGuard }) => {
    void consoleGuard;
    await login(page);

    // The security property this design exists for: a successful XSS must not be
    // able to steal a long-lived credential.
    const exposed = await page.evaluate(() => ({
      localStorage: JSON.stringify(window.localStorage),
      sessionStorage: JSON.stringify(window.sessionStorage),
      cookies: document.cookie,
    }));

    expect(exposed.localStorage).not.toContain('eyJ'); // no JWT anywhere
    expect(exposed.sessionStorage).not.toContain('eyJ');
    // httpOnly, so it is invisible to document.cookie...
    expect(exposed.cookies).not.toContain('erp_refresh');

    // ...but the browser does hold it, and does send it.
    const cookie = (await context.cookies()).find((c) => c.name === 'erp_refresh');
    expect(cookie, 'the refresh cookie should exist in the cookie jar').toBeDefined();
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.sameSite).toBe('Lax');
    expect(cookie?.path).toBe('/api/v1/auth/');
  });

  test('logging out clears the session', async ({ page, consoleGuard }) => {
    void consoleGuard;
    await login(page);

    await page.getByRole('button', { name: /Cerrar sesión/i }).click();
    await page.waitForURL(/\/login/, { timeout: 20_000 });

    // Going back to a guarded route must not restore the session.
    await page.goto('/es/dashboard');
    await expect(page).toHaveURL(/\/login/, { timeout: 20_000 });
  });

  test('login is reachable in both locales', async ({ page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/en/login');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Sign in');

    await page.goto('/es/login');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Iniciar sesión');
  });
});
