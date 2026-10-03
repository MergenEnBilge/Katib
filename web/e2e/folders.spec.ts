import { expect, test } from '@playwright/test';
import {
  connectLibrary,
  UPLOAD_SET,
  UPLOAD_SET_IMAGE,
  UPLOAD_SET_LABEL,
  UPLOAD_SET_YAML,
  png,
  ROOT,
} from './fixtures';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

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

  await dialog.getByRole('button', { name: /Look for new or missing images/ }).click();
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
  await dialog.getByLabel('Copy a folder').setInputFiles(UPLOAD_SET);

  await expect(dialog.getByText('1 image added.')).toBeVisible();
  await expect(dialog.getByText(/already had labels/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Done' }).click();

  test.skip(test.info().project.name === 'phone', 'The class panel is a slide-over on a phone.');
  await expect(page.getByRole('button', { name: 'car 1' })).toBeVisible();
});

test('upload loose pictures and a label file together, with no folder', async ({ page }) => {
  // The same batch pipeline as a folder upload, just fed a flat file selection instead -- for
  // when someone has a picture and its label sitting in different places, not one tidy folder.
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Loose ${test.info().project.name}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  await page.getByRole('button', { name: 'Import images' }).last().click();
  const dialog = page.getByRole('dialog');
  await dialog
    .getByLabel('Copy pictures and labels')
    .setInputFiles([UPLOAD_SET_YAML, UPLOAD_SET_IMAGE, UPLOAD_SET_LABEL]);

  await expect(dialog.getByText('1 image added.')).toBeVisible();
  await expect(dialog.getByText(/already had labels/)).toBeVisible();
});

test('shows which file is uploading while a folder goes up', async ({ page }) => {
  // A folder goes up one file at a time. Slowing each request down is what makes that visible to
  // a test reliably, rather than hoping it lands mid-upload on a fast local server.
  await page.route('**/folders:upload-file', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 300));
    await route.continue();
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Progress ${test.info().project.name}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  await page.getByRole('button', { name: 'Import images' }).last().click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Copy a folder').setInputFiles(UPLOAD_SET);

  await expect(page.getByText(/Uploading .+…/)).toBeVisible();
  await expect(page.getByRole('progressbar', { name: 'Import progress' })).toBeVisible();
  await expect(dialog.getByText('1 image added.')).toBeVisible();
});

test('pictures deleted from a connected folder can be taken out of the project', async ({ page }) => {
  // A folder of its own: the shared library is in use by other tests at the same time.
  const folder = join(ROOT, `vanishing-${test.info().project.name}`);
  rmSync(folder, { recursive: true, force: true });
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, 'keep.png'), png(64, 48, [30, 90, 160]));
  writeFileSync(join(folder, 'gone.png'), png(64, 48, [160, 60, 30]));

  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Vanishing ${test.info().project.name}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await page.getByRole('button', { name: 'Import images' }).last().click();
  const dialog = page.getByRole('dialog');
  await page.getByText('Type a folder path instead').click();
  await page.getByLabel('Folder on the Katib computer').fill(folder);
  await page.getByRole('button', { name: 'Connect', exact: true }).click();
  await expect(dialog.getByText('2 images added.')).toBeVisible();
  await expect(dialog.getByText('Read in place')).toBeVisible();

  rmSync(join(folder, 'gone.png'));
  await dialog.getByRole('button', { name: /Look for new or missing images/ }).click();
  await expect(dialog.getByText(/1 picture in this project is no longer in/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Take them out' }).click();
  await expect(dialog.getByText('1 missing picture taken out of the project.')).toBeVisible();
  // The file that is still there was never touched.
  expect(existsSync(join(folder, 'keep.png'))).toBe(true);
});
