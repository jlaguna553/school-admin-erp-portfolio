import { expect, type Page } from '@playwright/test';

import { authedTest as test, content, unique } from './fixtures';

/**
 * The gradebook.
 *
 * The rule that matters most is that an unmarked cell is not a zero. A grid
 * showing every student failing until the last exam is marked would be worse
 * than no grid at all, so it is asserted directly rather than assumed.
 *
 * Every test opens its own evaluation period. Averages are per period, so
 * sharing one would let a mark left by an earlier test change the number a
 * later one is checking — which is how the billing tests came to fail on data
 * rather than on behaviour.
 */
async function openPeriod(page: Page): Promise<void> {
  await page.goto('/es/grades');
  await content(page).getByRole('button', { name: /Nuevo periodo/i }).click();

  const dialog = page.getByRole('dialog');
  await dialog.locator('#term_name').fill(unique('Periodo'));
  // A year may hold only one period per position, so each run claims its own
  // rather than colliding with whatever the school already had.
  await dialog.locator('#ordinal').fill(String((Date.now() % 30_000) + 10));
  await dialog.locator('#start_date').fill('2026-09-01');
  await dialog.locator('#end_date').fill('2026-12-15');
  await dialog.getByRole('button', { name: /Guardar/i }).click();
  await expect(dialog).toBeHidden({ timeout: 20_000 });
}

async function addAssessment(page: Page, name: string) {
  await content(page).getByRole('button', { name: /Nueva evaluaci/i }).click();

  const dialog = page.getByRole('dialog');
  await dialog.locator('#name').fill(name);
  await dialog.locator('#max_score').fill('10.00');
  await dialog.getByRole('button', { name: /Guardar/i }).click();
  await expect(dialog).toBeHidden({ timeout: 20_000 });

  const table = content(page).locator('table');
  await expect(table).toBeVisible({ timeout: 20_000 });
  return table;
}

/** Pick the period this test just opened, not whichever was current. */
async function selectNewestPeriod(page: Page) {
  const select = content(page).locator('#gb-term');
  await select.click();
  await page.getByRole('option').last().click();
}

test.describe('Gradebook', () => {
  test('marks a column and saves it', async ({ authedPage: page }) => {
    await openPeriod(page);
    await selectNewestPeriod(page);
    const table = await addAssessment(page, unique('Examen'));

    await table.locator('tbody tr').first().getByRole('textbox').last().fill('8');
    await table.getByRole('button', { name: /Guardar/i }).first().click();

    await expect(page.getByText(/Calificaciones guardadas/i)).toBeVisible({ timeout: 20_000 });
  });

  test('an unmarked student reads as nothing, not as zero', async ({ authedPage: page }) => {
    await openPeriod(page);
    await selectNewestPeriod(page);
    const table = await addAssessment(page, unique('Sin calificar'));

    // Nothing marked in this period, so every average is a dash. A zero here
    // would say the whole class failed an exam nobody has sat.
    const averages = await table.locator('tbody tr td:last-child').allTextContents();
    expect(averages.length).toBeGreaterThan(0);
    for (const text of averages) {
      expect(text).toContain('—');
      expect(text).toContain('(0)');
    }
  });

  test('the average counts only what has been marked', async ({ authedPage: page }) => {
    await openPeriod(page);
    await selectNewestPeriod(page);
    const table = await addAssessment(page, unique('Parcial'));

    const first = table.locator('tbody tr').first();
    await first.getByRole('textbox').last().fill('9');
    await table.getByRole('button', { name: /Guardar/i }).first().click();
    await expect(page.getByText(/Calificaciones guardadas/i)).toBeVisible({ timeout: 20_000 });

    // One mark out of ten, on its own in the period.
    await expect(first.locator('td').last()).toContainText('(1)', { timeout: 20_000 });
    // And everyone else still reads as unmarked rather than as zero.
    await expect(table.locator('tbody tr').nth(1).locator('td').last()).toContainText('—');
  });
});
