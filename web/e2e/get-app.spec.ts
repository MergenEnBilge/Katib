import { expect, test } from '@playwright/test';

test('the code for the Android app opens a page with a download button', async ({ page }) => {
  await page.goto('/get-app');
  await expect(page.getByRole('heading', { name: 'Get Katib' })).toBeVisible();
  const download = page.getByRole('link', { name: 'Download the Android app' });
  await expect(download).toHaveAttribute('href', /Katib-android\.apk$/);
});
