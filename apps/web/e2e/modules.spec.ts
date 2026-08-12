import { authedTest as test, content, expect, unique } from './fixtures';

test.describe('Dashboard', () => {
  test('shows KPI figures from the API', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;

    const kpis = content(page).locator('p.tabular');
    await expect(kpis.first()).toBeVisible();
    // Values start as an em dash and resolve to a number once loaded.
    await expect(kpis.first()).not.toHaveText('—', { timeout: 20_000 });
  });

  test('the chart offers a table view', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;

    await page.getByRole('button', { name: /Ver tabla/i }).click();
    await expect(page.getByRole('button', { name: /Ver gráfico/i })).toBeVisible();
    // Seven weekdays of data.
    await expect(content(page).locator('table tbody tr')).toHaveCount(7 + 3);
  });
});

test.describe('Students', () => {
  test('lists students with pagination metadata', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/students');

    await expect(content(page).getByRole('heading', { name: 'Estudiantes' })).toBeVisible();
    await expect(content(page).locator('table tbody tr').first()).toBeVisible({ timeout: 20_000 });
    await expect(content(page).getByText(/registros · página/)).toBeVisible();
  });

  test('search narrows the result set', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/students');
    await expect(content(page).locator('table tbody tr').first()).toBeVisible({ timeout: 20_000 });

    await content(page).getByRole('searchbox').fill('zzz-no-such-student-zzz');
    await expect(page.getByText('No se encontraron usuarios')).toBeVisible({
      timeout: 20_000,
    });
  });

  test('creates a student, then deactivates them', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    await page.goto('/es/students');

    const surname = unique('E2E');
    const email = `${surname.toLowerCase()}@e2e.test`;

    await page.getByRole('button', { name: /Nuevo/ }).click();
    await page.fill('#first_name', 'Prueba');
    await page.fill('#last_name', surname);
    await page.fill('#email', email);
    await page.fill('#password', 'E2ePassword!2026');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByText('Usuario creado')).toBeVisible({ timeout: 20_000 });

    // Find the new row via search.
    await content(page).getByRole('searchbox').fill(surname);
    const row = page.locator('table tbody tr', { hasText: surname });
    await expect(row).toBeVisible({ timeout: 20_000 });

    // Deactivating is a soft delete: the row leaves the default list but the
    // record is retained server-side.
    await row.getByRole('button', { name: /Desactivar/ }).click();
    await page.getByRole('button', { name: 'Desactivar' }).last().click();

    await expect(page.getByText(/ha sido desactivado/)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText('No se encontraron usuarios')).toBeVisible({
      timeout: 20_000,
    });
  });

  test('surfaces the API duplicate-email error on the field', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    await page.goto('/es/students');
    await expect(content(page).locator('table tbody tr').first()).toBeVisible({ timeout: 20_000 });

    await page.getByRole('button', { name: /Nuevo/ }).click();
    await page.fill('#first_name', 'Duplicado');
    await page.fill('#last_name', 'Correo');
    // Seeded by `seed_demo`.
    await page.fill('#email', 'student1@example.test');
    await page.fill('#password', 'E2ePassword!2026');
    await page.getByRole('button', { name: 'Guardar' }).click();

    // The server's per-field detail is mapped onto the email input.
    await expect(page.locator('#email-error')).toBeVisible({ timeout: 20_000 });
  });
});

test.describe('Academic', () => {
  test('switches between years and programmes', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    await page.goto('/es/academic');

    await expect(page.getByRole('tab', { name: 'Años académicos' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(content(page).locator('table tbody tr').first()).toBeVisible({ timeout: 20_000 });

    await page.getByRole('tab', { name: 'Programas' }).click();
    await expect(page.getByRole('tab', { name: 'Programas' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    await expect(content(page).getByText('Educación Primaria')).toBeVisible({ timeout: 20_000 });
  });

  test('programme names follow the active locale', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;

    await page.goto('/es/academic');
    await page.getByRole('tab', { name: 'Programas' }).click();
    await expect(content(page).getByText('Educación Primaria')).toBeVisible({ timeout: 20_000 });

    // The same record, requested in English, comes back translated.
    await page.goto('/en/academic');
    await page.getByRole('tab', { name: 'Programmes' }).click();
    await expect(content(page).getByText('Primary Education')).toBeVisible({ timeout: 20_000 });
  });

  test('creates a programme with both translations', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    await page.goto('/es/academic');
    await page.getByRole('tab', { name: 'Programas' }).click();

    const code = unique('P').slice(0, 12).toUpperCase();

    await page.getByRole('button', { name: /Nuevo programa/ }).click();
    await page.fill('#code', code);
    await page.fill('#name_es', 'Programa de prueba');
    await page.fill('#name_en', 'Test programme');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByText('Programa creado')).toBeVisible({ timeout: 20_000 });

    // Assert on the run-unique code: the suite is run repeatedly against the
    // same school, so the display name is not distinctive on its own.
    const esRow = content(page).locator('table tbody tr', { hasText: code });
    await expect(esRow).toContainText('Programa de prueba', { timeout: 20_000 });

    // The same record resolves to English on the English route.
    await page.goto('/en/academic');
    await page.getByRole('tab', { name: 'Programmes' }).click();
    const enRow = content(page).locator('table tbody tr', { hasText: code });
    await expect(enRow).toContainText('Test programme', { timeout: 20_000 });
  });

  test('rejects an end date before the start date', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    await page.goto('/es/academic');

    await page.getByRole('button', { name: /Nuevo año/ }).click();
    await page.fill('#name', unique('Y'));
    await page.fill('#start_date', '2030-09-01');
    await page.fill('#end_date', '2030-08-01');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.locator('#end_date-error')).toBeVisible();
  });
});

test.describe('Subjects', () => {
  test('lists subjects and filters by programme', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    await page.goto('/es/subjects');

    // Wait for real data, not the loading skeleton -- skeleton rows are also
    // `tbody tr`, so counting rows too early compares placeholders.
    await expect(content(page).getByRole('cell', { name: 'MAT' }).first()).toBeVisible({
      timeout: 20_000,
    });

    await page.getByRole('combobox', { name: /Filtrar por programa/ }).click();
    const option = page.getByRole('option').nth(1);
    const optionLabel = (await option.textContent()) ?? '';
    const programCode = optionLabel.split('—')[0]!.trim();
    await option.click();

    // Every remaining row must belong to the selected programme.
    await expect
      .poll(
        async () => {
          const badges = await content(page)
            .locator('table tbody tr td:nth-child(3)')
            .allTextContents();
          return badges.length > 0 && badges.every((text) => text.trim() === programCode);
        },
        { timeout: 20_000 },
      )
      .toBe(true);
  });

  test('creates a subject assigned to a programme', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    await page.goto('/es/subjects');
    await expect(content(page).locator('table tbody tr').first()).toBeVisible({ timeout: 20_000 });

    const code = unique('S').slice(0, 10).toUpperCase();

    await page.getByRole('button', { name: /Nueva asignatura/ }).click();
    await page.fill('#code', code);
    await page.fill('#name', 'Asignatura de prueba');
    await page.getByRole('combobox').filter({ hasText: /Selecciona un programa/ }).click();
    await page.getByRole('option').first().click();
    await page.fill('#credits', '4');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByText('Asignatura creada')).toBeVisible({ timeout: 20_000 });
  });
});

/**
 * Issue a fresh invoice, so the billing tests bring their own data.
 *
 * They used to rely on the seed containing something still unpaid, which made
 * them quietly consume it: recording a payment moves an invoice out of
 * "Emitida", so on a database the suite had run against a few times there were
 * none left and the tests began failing on data rather than on behaviour.
 */
async function issueInvoice(page: import('@playwright/test').Page) {
  await page.goto('/es/billing');
  await content(page).getByRole('button', { name: /Nueva factura/ }).click();

  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox').first().click();
  await page.getByRole('option').first().click();

  await dialog.locator('#lines\\.0\\.description').fill(unique('Concepto'));
  await dialog.locator('#lines\\.0\\.unit_price').fill('500.00');
  await dialog.getByRole('button', { name: /Emitir factura/ }).click();

  await expect(dialog).toBeHidden({ timeout: 30_000 });
}

/**
 * Open the detail dialog for an invoice that still has a balance.
 *
 * Applying the status filter triggers a refetch, so the test must wait until
 * every row really is "Emitida" before clicking — otherwise the click races the
 * re-render and opens whichever invoice occupied that row beforehand.
 */
async function openIssuedInvoice(page: import('@playwright/test').Page) {
  await issueInvoice(page);

  await page.goto('/es/billing');
  await page.getByRole('combobox', { name: /Filtrar por estado/ }).click();
  await page.getByRole('option', { name: 'Emitida' }).click();

  await expect
    .poll(
      async () => {
        const statuses = await content(page)
          .locator('table tbody tr td:nth-child(6)')
          .allTextContents();
        return statuses.length > 0 && statuses.every((text) => text.includes('Emitida'));
      },
      { timeout: 20_000 },
    )
    .toBe(true);

  await content(page).getByRole('button', { name: /Ver factura/ }).first().click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  // The dialog renders a skeleton until the invoice arrives.
  await expect(dialog.getByRole('heading').first()).toContainText('INV-', {
    timeout: 20_000,
  });
  return dialog;
}

test.describe('Billing', () => {
  test('lists invoices with status badges', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/billing');

    await expect(content(page).getByRole('heading', { name: 'Facturación' })).toBeVisible();
    await expect(content(page).locator('table tbody tr').first()).toBeVisible({ timeout: 20_000 });
  });

  test('filters by status', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/billing');
    await expect(content(page).locator('table tbody tr').first()).toBeVisible({ timeout: 20_000 });

    await page.getByRole('combobox', { name: /Filtrar por estado/ }).click();
    await page.getByRole('option', { name: 'Vencida' }).click();

    await expect(content(page).getByText(/registros · página/)).toBeVisible({ timeout: 20_000 });
  });

  test('opens an invoice and records a payment', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    const dialog = await openIssuedInvoice(page);

    // The enrollment panel is resolved through the academic service, not a JOIN.
    await expect(dialog.getByText(/^Matrícula:/)).toBeVisible();

    await dialog.getByRole('button', { name: /Registrar pago/ }).click();
    await page.fill('#amount', '10');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByText('Pago registrado')).toBeVisible({ timeout: 20_000 });
  });

  test('refuses a payment larger than the balance', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    const dialog = await openIssuedInvoice(page);

    await dialog.getByRole('button', { name: /Registrar pago/ }).click();

    await page.fill('#amount', '999999');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.locator('#amount-error')).toBeVisible();
  });
});

test.describe('Settings', () => {
  test('shows the resolved institution', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/settings');

    await expect(content(page).getByRole('heading', { name: 'Configuración' })).toBeVisible();
    await expect(content(page).getByText('Northfield School')).toBeVisible();
    await expect(content(page).getByText('northfield', { exact: true })).toBeVisible();
  });

  test('email is read-only', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/settings');
    await expect(page.locator('#settings-email')).toBeDisabled();
  });

  test('saves the profile', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/settings');

    const phone = `+34 ${Math.floor(100000000 + Math.random() * 899999999)}`;
    await page.fill('#settings-phone', phone);
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByText('Perfil actualizado')).toBeVisible({ timeout: 20_000 });

    await page.reload();
    await expect(page.locator('#settings-phone')).toHaveValue(phone, { timeout: 20_000 });
  });

  test('rejects a wrong current password', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;
    await page.goto('/es/settings');

    await page.fill('#current_password', 'not-the-password');
    await page.fill('#new_password', 'Whatever!2026pass');
    await page.fill('#confirm_password', 'Whatever!2026pass');
    await page.getByRole('button', { name: 'Cambiar contraseña' }).click();

    await expect(page.locator('#current_password-error')).toBeVisible({ timeout: 20_000 });
  });

  test('catches mismatched confirmation before sending', async ({
    authedPage: page,
    consoleGuard,
  }) => {
    void consoleGuard;
    await page.goto('/es/settings');

    await page.fill('#current_password', 'anything');
    await page.fill('#new_password', 'Whatever!2026pass');
    await page.fill('#confirm_password', 'Different!2026pass');
    await page.getByRole('button', { name: 'Cambiar contraseña' }).click();

    await expect(page.locator('#confirm_password-error')).toBeVisible();
  });
});

test.describe('Navigation', () => {
  test('every sidebar entry resolves', async ({ authedPage: page, consoleGuard }) => {
    void consoleGuard;

    for (const [label, path] of [
      ['Estudiantes', '/es/students'],
      ['Académico', '/es/academic'],
      ['Asignaturas', '/es/subjects'],
      ['Horarios', '/es/schedule'],
      ['Facturación', '/es/billing'],
      ['Configuración', '/es/settings'],
    ] as const) {
      await page.getByRole('link', { name: label, exact: true }).click();
      await page.waitForURL(new RegExp(path.replace('/', '\\/')));
      await expect(page.locator('aside')).toBeVisible();
    }
  });
});
