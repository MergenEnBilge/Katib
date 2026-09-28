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

test('the tour opens the slide-over panels it points at on a phone', async ({ page }) => {
  test.skip(test.info().project.name !== 'phone', 'This is exactly the layout that broke.');

  await page.goto('/');
  await page.getByRole('button', { name: 'Try it with practice pictures' }).click();

  const tour = page.getByRole('dialog', { name: 'Welcome to your workspace' });
  await expect(tour).toBeVisible();
  await tour.getByRole('button', { name: 'Next' }).click();

  // "Your pictures" points at the image list, which is a closed slide-over on a phone. It used
  // to show a blank dimmed screen here instead of opening it.
  await expect(page.getByRole('dialog', { name: 'Your pictures' })).toBeVisible();
  await expect(page.getByRole('complementary', { name: 'Images' })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Next' }).click();

  // Same for "Classes", in the other slide-over.
  await expect(page.getByRole('dialog', { name: 'Classes' })).toBeVisible();
  await expect(page.getByRole('complementary', { name: 'Classes and details' })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Next' }).click();
  await expect(page.getByRole('dialog', { name: 'Drawing tools' })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Next' }).click();

  // "Try it: draw a box" waits for a real shape, which this test does not draw -- skipping past
  // it still has to work without the panel it needs next getting in its own way.
  await expect(page.getByRole('dialog', { name: 'Try it: draw a box' })).toBeVisible();
  await page.getByRole('button', { name: 'Skip this step' }).click();

  // "Finish a picture" lives in the same panel as Classes, no drawing needed to reach it.
  await expect(page.getByRole('dialog', { name: 'Finish a picture' })).toBeVisible();

  // Everything after this that is not a toolbar button a phone hides outright (split, export,
  // help) should be skipped straight past, without ever stalling on a dimmed screen with no
  // target to show. Clicking through has to reach the end within a small, bounded number of
  // steps rather than needing to be rescued from a stuck dialog.
  for (let i = 0; i < 10 && (await page.getByRole('dialog').count()) > 0; i++) {
    await page.getByRole('dialog').getByRole('button', { name: /Next|Finish/ }).click();
  }
  await expect(page.getByRole('dialog')).toBeHidden();
});

test('the help window can start the tour again', async ({ page }) => {
  test.skip(test.info().project.name === 'phone', 'The toolbar is trimmed on a phone.');
  await page.goto('/');
  await page.getByRole('button', { name: 'Help', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Help' })).toBeVisible();
  await expect(page.getByRole('link', { name: /Read the guide/ })).toBeVisible();
});
