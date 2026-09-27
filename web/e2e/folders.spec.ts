import { expect, test } from '@playwright/test';
import { connectLibrary, UPLOAD_SET } from './fixtures';

test('browse for a folder, connect it and look for new images', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Folders ${test.info().project.name}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  await page.getByRole('button', { name: 'Import images' }).last().click();
  await page.getByRole('button', { name: 'Connect a folder' }).click();

  // The picker starts from the places people know and lets them walk down from there.
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Home' }).click();
  await expect(dialog.getByRole('button', { name: 'Use this folder' })).toBeEnabled();
  await expect(dialog.getByRole('button', { name: 'Up one folder' })).toBeEnabled();
  await dialog.getByRole('button', { name: 'Cancel' }).click();

  await connectLibrary(page);
  await expect(dialog.getByText('3 images added.')).toBeVisible();
  await expect(dialog.getByRole('list', { name: 'Connected folders' })).toBeVisible();

  await dialog.getByRole('button', { name: /Look for new images/ }).click();
  await expect(dialog.getByText('0 images added.')).toBeVisible();
});

test('upload a folder that already has labels', async ({ page }) => {
  // The way in when Katib cannot browse the computer it runs on: the browser sends the folder
  // instead of a path, and Katib reads the data.yaml and labels that came along with it.
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Upload ${test.info().project.name}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  await page.getByRole('button', { name: 'Import images' }).last().click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Upload a folder').setInputFiles(UPLOAD_SET);

  await expect(dialog.getByText('1 image added.')).toBeVisible();
  await expect(dialog.getByText(/already had labels/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Done' }).click();

  test.skip(test.info().project.name === 'phone', 'The class panel is a slide-over on a phone.');
  await expect(page.getByRole('button', { name: 'car 1' })).toBeVisible();
});
