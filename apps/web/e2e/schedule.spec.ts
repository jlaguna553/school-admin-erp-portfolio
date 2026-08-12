import { expect, type Page } from '@playwright/test';

import { authedTest as test, content, unique } from './fixtures';

/**
 * Timetable and register.
 *
 * Two claims are worth asserting through the browser rather than trusting from
 * the API tests: that a double-booking is refused *on the form*, where somebody
 * can act on it, and that a student nobody marked stays unmarked. The second is
 * the attendance equivalent of the gradebook's "an empty cell is not a zero",
 * and getting it wrong would manufacture attendance records for a roll nobody
 * took.
 */

/** The next Monday, so the day always has seeded classes on it. */
function nextMonday(): string {
  const day = new Date();
  day.setUTCDate(day.getUTCDate() + ((8 - day.getUTCDay()) % 7 || 7));
  return day.toISOString().slice(0, 10);
}

async function openTimetable(page: Page) {
  await page.goto('/es/schedule');
  // The seeded school has groups; the first is selected automatically.
  await expect(content(page).locator('#tt-group')).toBeVisible({ timeout: 20_000 });
}

test.describe('Timetable', () => {
  test('shows the seeded week for a group', async ({ authedPage: page }) => {
    await openTimetable(page);

    const monday = content(page).getByRole('region', { name: 'Lunes' });
    await expect(monday).toBeVisible({ timeout: 20_000 });
    // Weekend columns stay hidden unless something is scheduled on them.
    await expect(content(page).getByRole('region', { name: 'Domingo' })).toBeHidden();
  });

  test('refuses to double-book the group, on the field that can be changed', async ({
    authedPage: page,
  }) => {
    await openTimetable(page);

    // Read the hour of an existing Monday class and try to reuse it.
    const monday = content(page).getByRole('region', { name: 'Lunes' });
    const existing = monday.getByRole('button').first();
    const label = (await existing.textContent()) ?? '';
    const [start] = label.match(/\d{2}:\d{2}/g) ?? [];
    expect(start, 'the seeded school should have a Monday class').toBeTruthy();

    await monday.getByRole('button', { name: /Añadir clase/i }).click();

    const dialog = page.getByRole('dialog');
    await dialog.locator('#slot_start').fill(start!);
    await dialog.locator('#slot_end').fill('23:00');
    await dialog.getByRole('button', { name: /Guardar/i }).click();

    // Still open, with the clash explained rather than a toast that scrolls away.
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(/ya tiene/i)).toBeVisible({ timeout: 20_000 });
  });

  test('creates a group', async ({ authedPage: page }) => {
    await openTimetable(page);
    await content(page).getByRole('button', { name: /Nuevo grupo/i }).click();

    const dialog = page.getByRole('dialog');
    await dialog.locator('#group_name').fill(unique('G'));
    await dialog.getByRole('button', { name: /Guardar/i }).click();

    await expect(dialog).toBeHidden({ timeout: 20_000 });
    await expect(page.getByText(/Grupo creado/i)).toBeVisible({ timeout: 20_000 });
  });
});

test.describe('Attendance', () => {
  test('takes the roll and marks the class as done', async ({ authedPage: page }) => {
    await page.goto('/es/attendance');
    await content(page).locator('#roll-date').fill(nextMonday());

    const classes = content(page).getByRole('button').filter({ hasText: /\d{2}:\d{2}/ });
    await expect(classes.first()).toBeVisible({ timeout: 20_000 });
    await classes.first().click();

    // Everyone unmarked to begin with: nobody has looked at this class.
    await expect(content(page).getByText(/^0 de \d+ marcados$/)).toBeVisible({ timeout: 20_000 });

    const roll = content(page).getByRole('group').first();
    await roll.getByRole('button', { name: 'Presente' }).click();

    await content(page).getByRole('button', { name: /Guardar lista/i }).click();
    await expect(page.getByText(/Lista guardada/i)).toBeVisible({ timeout: 20_000 });

    // One marked, the rest still unrecorded — not silently marked present.
    await expect(content(page).getByText(/^1 de \d+ marcados$/)).toBeVisible({ timeout: 20_000 });
    await expect(content(page).getByText('Pasada').first()).toBeVisible();
  });

  test('a day with no classes says so', async ({ authedPage: page }) => {
    await page.goto('/es/attendance');
    // The Sunday after next Monday: the seeded timetable is Monday to Friday.
    const sunday = new Date(`${nextMonday()}T00:00:00Z`);
    sunday.setUTCDate(sunday.getUTCDate() + 6);
    await content(page).locator('#roll-date').fill(sunday.toISOString().slice(0, 10));

    await expect(content(page).getByText(/No hay clases programadas/i)).toBeVisible({
      timeout: 20_000,
    });
  });
});
