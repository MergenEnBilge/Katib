import { expect, test, type Page } from '@playwright/test';
import { join } from 'node:path';
import { OUT } from '../screenshots.config';

// First-use tips are helpful in the app and clutter in a picture of it.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('katib.tips', JSON.stringify({ seen: [], off: true }));
  });
});

const shot = async (page: Page, name: string): Promise<void> => {
  await page.waitForTimeout(400); // let the canvas and any fade finish
  await page.screenshot({ path: join(OUT, `${name}.png`) });
};

/** Make the practice project, leave the tour, and land on the picture that is already labeled. */
async function openPractice(page: Page): Promise<void> {
  await page.goto('/');
  await page.getByRole('button', { name: 'Try it with practice pictures' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}/, { timeout: 60_000 });
  await page.getByRole('button', { name: 'Skip the tour' }).click();
  await expect(page.getByRole('button', { name: /Save status/ })).toBeVisible();
  await page.getByRole('button', { name: /practice-1\.png/ }).first().click();
  // The canvas is two layers, the picture and the shapes drawn over it.
  await expect(page.locator('canvas').first()).toBeVisible();
}

test('the pictures for the readme', async ({ page }) => {
  await openPractice(page);
  await shot(page, 'workspace');

  await page.getByRole('button', { name: 'Dataset health' }).click();
  await expect(page.getByRole('dialog', { name: /health/i })).toBeVisible();
  await shot(page, 'health');
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: 'Train, validation and test split' }).click();
  await expect(page.getByRole('dialog', { name: 'Train, validation and test' })).toBeVisible();
  await shot(page, 'splits');
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: 'Class gallery' }).click();
  await expect(page.getByRole('heading', { name: /gallery/i })).toBeVisible();
  await shot(page, 'gallery');

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
  await shot(page, 'projects');

  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await shot(page, 'settings');
});
