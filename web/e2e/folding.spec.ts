import { expect, test } from '@playwright/test';
import { connectLibrary } from './fixtures';

test('the sidebar folds away and is still folded after a reload', async ({ page }) => {
  test.skip(test.info().project.name === 'phone', 'A phone shows the navigation as a top bar.');

  await page.goto('/');
  const sidebar = page.locator('aside.sidebar');
  await expect(sidebar.getByRole('link', { name: 'Projects' })).toBeVisible();
  const wide = (await sidebar.boundingBox())?.width ?? 0;

  await page.getByRole('button', { name: 'Fold the sidebar away' }).click();
  const narrow = (await sidebar.boundingBox())?.width ?? 0;
  expect(narrow).toBeLessThan(wide);
  // The links stay, so you can still navigate from the folded strip.
  await expect(sidebar.getByRole('link', { name: 'Settings' })).toBeVisible();

  await page.reload();
  await expect(page.getByRole('button', { name: 'Show the sidebar' })).toBeVisible();
  expect((await sidebar.boundingBox())?.width ?? 0).toBe(narrow);

  await page.getByRole('button', { name: 'Show the sidebar' }).click();
  expect((await sidebar.boundingBox())?.width ?? 0).toBe(wide);
});

test('the side panel folds away with a key and comes back', async ({ page }) => {
  test.skip(test.info().project.name === 'phone', 'The panel is a slide-over on a phone.');

  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Folding ${Date.now()}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  await page.getByRole('button', { name: 'Import images' }).last().click();
  await connectLibrary(page);
  await expect(page.getByText('images added.')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();

  const panel = page.locator('aside.panel-wrap');
  const images = page.locator('aside.rail');
  await expect(panel).toBeVisible();

  await page.getByRole('button', { name: 'Fold the side panel away' }).click();
  await expect(panel).toBeHidden();
  await page.keyboard.press(']');
  await expect(panel).toBeVisible();

  // The image list uses the other bracket, and both choices survive a reload.
  const listWidth = (await images.boundingBox())?.width ?? 0;
  await page.keyboard.press('[');
  expect((await images.boundingBox())?.width ?? 0).toBeLessThan(listWidth);
  await page.keyboard.press(']');
  await expect(panel).toBeHidden();

  await page.reload();
  await expect(panel).toBeHidden();
  expect((await images.boundingBox())?.width ?? 0).toBeLessThan(listWidth);
});
