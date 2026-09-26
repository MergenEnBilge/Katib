import { expect, test } from '@playwright/test';

test('the workspaces dialog explains sharing and remembers other servers', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Local workspace' }).click();
  const dialog = page.getByRole('dialog', { name: 'Workspaces' });
  await expect(dialog.getByText('Katib is only open on this computer.')).toBeVisible();
  // It points at the mode in Settings rather than a command to retype.
  await expect(dialog.getByText('My team, on this network')).toBeVisible();

  await dialog.getByRole('tab', { name: 'Other servers' }).click();
  await dialog.getByLabel('Name').fill('Design team');
  await dialog.getByLabel('Address').fill('192.168.1.20:8420');
  await dialog.getByRole('button', { name: 'Save server' }).click();
  await expect(dialog.getByText('http://192.168.1.20:8420')).toBeVisible();

  await page.reload();
  await page.getByRole('button', { name: 'Local workspace' }).click();
  await page.getByRole('dialog').getByRole('tab', { name: 'Other servers' }).click();
  await expect(page.getByRole('dialog').getByText('Design team')).toBeVisible();
});
