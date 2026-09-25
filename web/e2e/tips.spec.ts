import { expect, test } from '@playwright/test';
import { connectLibrary } from './fixtures';

test('a tip appears the first time a tool is picked and stays away once dismissed', async ({ page }) => {
  test.skip(test.info().project.name === 'phone', 'Picking tools by key is a desktop flow.');

  await page.goto('/');
  await page.evaluate(() => localStorage.removeItem('katib.tips'));
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Tips ${Date.now()}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  await page.getByRole('button', { name: 'Import images' }).last().click();

  // Windows explain themselves the first time.
  await expect(page.getByRole('note', { name: /Tip: Bringing in pictures and labels/ })).toBeVisible();
  await connectLibrary(page);
  await expect(page.getByText('images added.')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();

  // Nothing floats over the canvas until someone picks a tool.
  await expect(page.getByRole('note', { name: /Tip:/ })).toBeHidden();
  await page.keyboard.press('b');
  const tip = page.getByRole('note', { name: 'Tip: Drawing boxes' });
  await expect(tip).toBeVisible();
  await tip.getByRole('button', { name: 'Got it' }).click();
  await expect(tip).toBeHidden();

  // Picking the tool again does not bring it back, even after a reload.
  await page.keyboard.press('v');
  await page.keyboard.press('b');
  await expect(page.getByRole('note', { name: 'Tip: Drawing boxes' })).toBeHidden();
  await page.reload();
  await page.keyboard.press('p');
  await expect(page.getByRole('note', { name: 'Tip: Drawing polygons' })).toBeVisible();
  await page.keyboard.press('b');
  await expect(page.getByRole('note', { name: 'Tip: Drawing boxes' })).toBeHidden();
});

test('tips can be switched off from the help window and turned back on', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.removeItem('katib.tips'));
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  const toggle = page.getByLabel('Show a short tip the first time I use a tool or window');
  await expect(toggle).toBeChecked();
  await toggle.uncheck();
  await page.keyboard.press('Escape');
  await page.goto('/settings');
  await expect(page.getByRole('note', { name: /Tip:/ })).toBeHidden();

  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await page.getByRole('button', { name: 'Show every tip again' }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Limits' }).click();
  await expect(page.getByRole('note', { name: 'Tip: Limits' })).toBeVisible();
});

test('the settings tour walks through the page', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await page.getByRole('button', { name: /Tour of Settings/ }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole('dialog', { name: 'Settings', exact: true })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Next' }).click();
  await expect(page.getByRole('dialog', { name: 'Sections' })).toBeVisible();
  await page.getByRole('button', { name: 'Skip the tour' }).click();
  await expect(page.getByRole('dialog', { name: 'Sections' })).toBeHidden();
});
