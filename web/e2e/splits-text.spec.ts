import { expect, test } from '@playwright/test';
import { connectLibrary } from './fixtures';

test('write a caption, divide the images into splits and keep both after a reload', async ({ page }) => {
  test.skip(test.info().project.name === 'phone', 'The toolbar is trimmed on a phone.');

  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Words ${Date.now()}`);
  await page.getByRole('checkbox', { name: /^Text/ }).check();
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  await page.getByRole('button', { name: 'Import images' }).last().click();
  await connectLibrary(page);
  await expect(page.getByText('images added.')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();

  // A caption on the first image.
  await page.getByRole('tab', { name: 'Text' }).click();
  await page.getByRole('button', { name: 'Add text' }).click();
  const caption = page.getByRole('textbox', { name: /Text 1/ });
  await caption.fill('A pale square on a dark background.');
  await caption.blur();
  await expect(page.getByRole('button', { name: /Save status: Saved/ })).toBeVisible();

  // Divide the images: everything to test, so the result is easy to check.
  await page.getByRole('button', { name: 'Train, validation and test split' }).click();
  const dialog = page.getByRole('dialog', { name: 'Train, validation and test' });
  await dialog.getByLabel('Train share').fill('0');
  await dialog.getByLabel('Validation share').fill('0');
  await dialog.getByLabel('Test share').fill('100');
  await expect(dialog.getByText(/would change split/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Split images' }).click();
  await expect(page.getByText(/You can undo this/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Close' }).click();

  await page.reload();
  await page.getByRole('tab', { name: 'Text' }).click();
  await expect(page.getByRole('textbox', { name: /Text 1/ })).toHaveValue(
    'A pale square on a dark background.',
  );
  await expect(page.getByLabel('Split for this image')).toHaveValue('test');
});
