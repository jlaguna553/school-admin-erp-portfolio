import { expect } from '@playwright/test';

import { content, login, loginAsPlatform, test, unique } from './fixtures';

/**
 * The platform operator's console.
 *
 * These exist because a whole class of defect gets past `tsc` and the API
 * tests: a table that renders, returns the right data, and shows nothing —
 * a cell collapsed to zero width reads as "no name" to a person and as a pass
 * to every other check. Only a browser catches it.
 */
test.describe('Platform console', () => {
  test('lists institutions with their names visible', async ({ page }) => {
    await loginAsPlatform(page);

    const table = content(page).getByRole('table');
    await expect(table).toBeVisible();

    // The paragraph holding the name, not the `<td>` around it. The cell keeps
    // its padding and stays "visible" even when its contents have collapsed to
    // zero width, so asserting on the cell passes while the column reads blank.
    const name = table.locator('tbody tr').first().locator('p').first();

    await expect(name).not.toBeEmpty();
    await expect(name).toBeVisible();

    const box = await name.boundingBox();
    expect(box, 'the name should occupy space').not.toBeNull();
    expect(box!.width).toBeGreaterThan(40);
  });

  test('provisions a school from nothing but a name', async ({ page }) => {
    await loginAsPlatform(page);

    const name = unique('Colegio');
    await content(page).getByRole('button', { name: /nueva instituci/i }).click();

    const dialog = page.getByRole('dialog');
    await dialog.locator('#name').fill(name);

    // Neither a hostname nor a schema is asked for any more.
    await expect(dialog.locator('#domain')).toHaveCount(0);
    await expect(dialog.locator('#schema_name')).toHaveCount(0);

    await dialog.getByRole('button', { name: /guardar/i }).click();
    await expect(dialog).toBeHidden({ timeout: 30_000 });

    // And it appears in the list, readable.
    await expect(content(page).getByText(name)).toBeVisible();
  });

  test('the people screen reaches its own table', async ({ page }) => {
    await loginAsPlatform(page);

    await page.getByRole('link', { name: /personas/i }).click();
    await page.waitForURL(/\/platform\/people/);

    await expect(content(page).getByRole('table')).toBeVisible();
  });
});

/**
 * Reach, seen from the browser.
 *
 * The API already refused all of this; what it could not do is stop the
 * interface offering it. A school administrator could open the operator console
 * and be shown its tables and its "new institution" button, each of which came
 * back 403 — the boundary held and the screen lied.
 */
test.describe('Reach', () => {
  test('a school administrator is turned away from the console', async ({ page }) => {
    await login(page);
    await page.goto('/es/platform');

    // Sent home rather than shown a console they cannot use.
    await page.waitForURL(/\/es\/dashboard/, { timeout: 15_000 });
    await expect(content(page).getByRole('button', { name: /nueva instituci/i })).toHaveCount(0);
  });

  test('and never sees a link to it', async ({ page }) => {
    await login(page);

    await expect(page.getByRole('link', { name: /instituciones/i })).toHaveCount(0);
    await expect(page.getByRole('link', { name: /equipo de plataforma/i })).toHaveCount(0);
  });

  test('an operator is turned away from a school module', async ({ page }) => {
    await loginAsPlatform(page);
    await page.goto('/es/billing');

    // They belong to no institution, so there is no billing to show them.
    await page.waitForURL(/\/es\/platform/, { timeout: 15_000 });
  });
});
