import { expect, test } from '@playwright/test';

test('change a limit in Settings and find it saved after a reload', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await page.getByRole('button', { name: 'Limits' }).click();

  const upload = page.getByLabel('Largest upload, in MB');
  await upload.fill('12');
  await upload.blur();
  await expect(page.getByText('1 change not saved')).toBeVisible();
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('No changes')).toBeVisible();

  await page.reload();
  await page.getByRole('button', { name: 'Limits' }).click();
  await expect(page.getByLabel('Largest upload, in MB')).toHaveValue('12');

  // Put it back so other runs start the same.
  await page.getByLabel('Largest upload, in MB').fill('50');
  await page.getByLabel('Largest upload, in MB').blur();
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('No changes')).toBeVisible();
});

test('a setting that needs a restart says so and offers the button', async ({ page }) => {
  await page.goto('/settings');
  await page.getByLabel('Port').fill('8497');
  await page.getByLabel('Port').blur();
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Some saved settings apply after Katib restarts.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Restart Katib now' })).toBeVisible();
  await expect(page.getByText('Needs a restart', { exact: true })).toBeVisible();

  // Undo the change. The port comes back to what is running, so nothing waits any more.
  await page.getByLabel('Port').fill('8499');
  await page.getByLabel('Port').blur();
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Some saved settings apply after Katib restarts.')).toBeHidden();
});

test('the backup tab explains what a backup holds', async ({ page }) => {
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Backup' }).click();
  await expect(page.getByText('What is in it')).toBeVisible();
  await page.getByRole('button', { name: 'Make a backup' }).click();
  await expect(page.getByRole('link', { name: 'Download backup' })).toBeVisible();
});
