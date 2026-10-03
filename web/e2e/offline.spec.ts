import { expect, test } from '@playwright/test';

test('the app opens without a connection and recovers when it returns', async ({ page, context }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();

  // Wait for the browser to install the offline worker, then reload so it controls the page.
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await expect.poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();

  await context.setOffline(false);
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
});

test('a server that stops answering is said so, and the page recovers by itself', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();

  // The server goes away: every request fails the way it does when nothing is listening.
  await page.route('**/api/v1/**', (route) => route.abort('connectionrefused'));
  await page.getByRole('searchbox').fill('anything');
  const banner = page.getByRole('status').filter({ hasText: "Katib's server is not answering" });
  await expect(banner).toBeVisible();

  await page.unroute('**/api/v1/**');
  await banner.getByRole('button', { name: 'Try now' }).click();
  await expect(banner).toBeHidden();
  await expect(page.getByText('Connected to Katib again.')).toBeVisible();
});

test('the app can be installed', async ({ page }) => {
  await page.goto('/');
  const href = await page.locator('link[rel="manifest"]').getAttribute('href');
  const manifest = await (await page.request.get(href ?? '')).json();
  expect(manifest.name).toBe('Katib');
  expect(manifest.display).toBe('standalone');
  for (const icon of manifest.icons) {
    expect((await page.request.get(icon.src)).ok()).toBe(true);
  }
});
