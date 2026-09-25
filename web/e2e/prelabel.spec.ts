import { expect, test } from '@playwright/test';

test('pre-labeling explains how to turn it on', async ({ page }) => {
  test.skip(test.info().project.name === 'phone', 'The toolbar button is hidden on a phone.');

  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Prelabel ${Date.now()}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  await page.getByRole('button', { name: 'Pre-label with a model' }).click();
  const dialog = page.getByRole('dialog', { name: 'Pre-label with a model' });
  await expect(dialog.getByText('Model pre-labeling is turned off.')).toBeVisible();
  await expect(dialog.getByText('enabled = true')).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Run the model' })).toHaveCount(0);
});
