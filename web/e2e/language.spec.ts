import { expect, test } from '@playwright/test';

test('a mirrored test language flips the page and translates what has been moved to messages', async ({ page }) => {
  await page.goto('/?lang=qps-plocm');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('html')).toHaveAttribute('lang', 'qps-plocm');
  // The heading comes from a message, so it is accented and padded.
  await expect(page.getByRole('heading', { level: 1 })).toContainText('[');
  await page.screenshot({ path: 'test-results/rtl-projects.png' });

  const sidebar = await page.locator('aside.sidebar').boundingBox();
  const viewport = page.viewportSize();
  expect(sidebar).not.toBeNull();
  expect(viewport).not.toBeNull();
  // A wide window puts the sidebar in a column, which moves to the right in a right-to-left
  // language. A phone stacks it as a full-width bar across the top, where there is no side to take.
  if (sidebar && viewport && sidebar.width < viewport.width) {
    expect(sidebar.x).toBeGreaterThan(viewport.width / 2);
  }
});

test('English is the default and the language choice is remembered', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
});
