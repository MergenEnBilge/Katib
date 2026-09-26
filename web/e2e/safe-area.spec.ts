import { expect, test, type Locator, type Page } from '@playwright/test';

/**
 * Phones draw apps under their own status bar, notch and gesture bar, and Android has done it by
 * default since version 15. Playwright cannot give a page real insets, but the app reads them
 * through four custom properties, so setting those puts the layout in the state a phone puts it
 * in. Each test measures where something sits before and after, because "it is far enough down"
 * can be true by accident, while "it moved by exactly the height of the notch" cannot.
 */
const TOP = 48;
const BOTTOM = 32;
const INSETS = `:root {
  --safe-top: ${TOP}px;
  --safe-right: 16px;
  --safe-bottom: ${BOTTOM}px;
  --safe-left: 16px;
}`;

async function top(where: Locator): Promise<number> {
  return (await where.boundingBox())?.y ?? -1;
}

async function overflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

test('the navigation moves clear of the status bar', async ({ page }) => {
  await page.goto('/');
  const projects = page.getByRole('link', { name: 'Projects' }).first();
  await expect(projects).toBeVisible();

  const before = await top(projects);
  await page.addStyleTag({ content: INSETS });
  expect(await top(projects)).toBe(before + TOP);
  expect(await overflow(page)).toBeLessThanOrEqual(1);
});

test('a dialog keeps clear of the notch and the gesture bar', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();

  const before = await top(dialog);
  await page.addStyleTag({ content: INSETS });
  const after = await top(dialog);
  // The dialog is centred, so more room at the top than the bottom pushes it down by half the
  // difference. What matters is that it moved at all: without the insets it does not.
  expect(after).toBeGreaterThan(before);
  expect(after).toBeGreaterThanOrEqual(TOP);

  const box = await dialog.boundingBox();
  const height = page.viewportSize()?.height ?? 0;
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(height - BOTTOM + 1);
});

test('a message never sits on the gesture bar', async ({ page }) => {
  await page.goto('/settings');
  await page.addStyleTag({ content: INSETS });
  const region = page.locator('.region');
  const bottom = await region.evaluate((node) => {
    const style = getComputedStyle(node);
    return Number.parseFloat(style.bottom);
  });
  expect(bottom).toBeGreaterThanOrEqual(BOTTOM);
});
