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

test('model help lists downloadable models beside bringing your own file', async ({ page }) => {
  // The actual download is not exercised here -- it is a real internet fetch, and this suite
  // never touches the real network. The backend has its own coverage for the fetch itself,
  // against a local server standing in for the real one.
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Model help' }).click();
  await expect(page.getByText('Download a model')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download', exact: true }).first()).toBeVisible();
  await expect(page.getByText('Or add your own files')).toBeVisible();
});

test('a factory reset needs RESET typed before it can run', async ({ page }) => {
  // The actual reset is not exercised here -- it would wipe the data every other test in this
  // run shares. This only checks the confirmation guards it correctly, then backs out.
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Storage' }).click();
  await page.getByRole('button', { name: 'Reset everything…' }).click();

  const dialog = page.getByRole('dialog');
  const confirm = dialog.getByRole('button', { name: 'Reset everything' });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel('Type "RESET" to confirm').fill('please');
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel('Type "RESET" to confirm').fill('reset');
  await expect(confirm).toBeEnabled();

  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(dialog).toBeHidden();
});
