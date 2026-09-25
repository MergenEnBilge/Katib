import { expect, test } from '@playwright/test';

test('the practice project opens with a tour that ends when the person draws a box', async ({ page }) => {
  test.skip(test.info().project.name === 'phone', 'Drawing precision is a desktop flow.');

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome to Katib' })).toBeVisible();
  await page.getByRole('button', { name: 'Try it with practice pictures' }).click();

  const tour = page.getByRole('dialog', { name: 'Welcome to your workspace' });
  await expect(tour).toBeVisible();
  await tour.getByRole('button', { name: 'Next' }).click();
  await expect(page.getByRole('dialog', { name: 'Your pictures' })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Next' }).click();
  await expect(page.getByRole('dialog', { name: 'Classes' })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Next' }).click();
  await expect(page.getByRole('dialog', { name: 'Drawing tools' })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Next' }).click();

  // The practice step waits for a real box on the second, unlabeled picture.
  await expect(page.getByRole('dialog', { name: 'Try it: draw a box' })).toBeVisible();
  await page.getByRole('button', { name: /^practice-2\.png/ }).click();
  await page.getByRole('button', { name: /^ball/ }).first().click();
  const canvas = page.getByRole('application', { name: 'Annotation canvas' });
  const box = await canvas.boundingBox();
  if (!box) throw new Error('canvas has no size');
  await page.keyboard.press('b');
  await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.4);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.6, { steps: 5 });
  await page.mouse.up();
  await expect(page.getByText('Nice. That is a label.')).toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Finish a picture' })).toBeVisible();

  // The rest can be skipped, and the checklist on the home page remembers the progress.
  await page.getByRole('button', { name: 'Skip the tour' }).click();
  await expect(page.getByRole('dialog', { name: 'Finish a picture' })).toBeHidden();
  await page.goto('/');
  await expect(page.getByText(/[2-9] of 6 done/)).toBeVisible();
});

test('the help window can start the tour again', async ({ page }) => {
  test.skip(test.info().project.name === 'phone', 'The toolbar is trimmed on a phone.');
  await page.goto('/');
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Help' })).toBeVisible();
  await expect(page.getByRole('link', { name: /Read the guide/ })).toBeVisible();
});
