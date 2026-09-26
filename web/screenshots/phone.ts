import { expect, test } from '@playwright/test';
import { join } from 'node:path';
import { OUT } from '../screenshots.config';

test('the same project on a phone', async ({ page }) => {
  await page.goto('/');
  // The practice project is already there, made by the desktop pass.
  await page.getByRole('link', { name: /Try Katib/ }).first().click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}/);
  await expect(page.locator('canvas').first()).toBeVisible();
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, 'phone.png') });
});
