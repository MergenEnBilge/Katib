import { expect, test } from '@playwright/test';
import { connectLibrary } from './fixtures';

const PASSWORD = 'correct horse battery';

test('two people work on one project: invite, presence and a read-only image', async ({
  browser,
  page,
}) => {
  // The first visit asks for an administrator.
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Set up Katib' })).toBeVisible();
  await page.getByLabel('Email').fill('admin@example.com');
  await page.getByLabel('Your name').fill('Ada Admin');
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Create administrator' }).click();
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill('Team project');
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  const projectUrl = page.url();

  await page.getByRole('button', { name: 'Import images' }).last().click();
  await connectLibrary(page);
  await expect(page.getByText('3 images added.')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();
  await page.getByLabel('New class name').fill('car');
  await page.getByRole('button', { name: 'Add', exact: true }).click();

  // Invite an annotator.
  await page.getByRole('button', { name: 'Team' }).click();
  const team = page.getByRole('dialog', { name: 'Team' });
  await team.getByRole('button', { name: 'Create invite link' }).click();
  const link = await team.getByLabel('Invite link').inputValue();
  expect(link).toContain('/invite/');
  await team.getByRole('button', { name: 'Done' }).click();

  // The second person opens the link in their own browser.
  const sam = await browser.newContext();
  const samPage = await sam.newPage();
  await samPage.goto(link);
  await expect(samPage.getByText(/invited to .Team project. as annotator/)).toBeVisible();
  await samPage.getByLabel('Email').fill('sam@example.com');
  await samPage.getByLabel('Your name').fill('Sam Rivera');
  await samPage.getByLabel('Password').fill(PASSWORD);
  await samPage.getByRole('button', { name: 'Create account' }).click();
  await expect(samPage.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
  await samPage.goto(projectUrl);

  // Each sees the other. Ada opened the first image first, so it is locked for Sam.
  await expect(page.getByRole('img', { name: 'Sam Rivera' })).toBeVisible({ timeout: 10_000 });
  await expect(samPage.getByRole('img', { name: 'Ada Admin' })).toBeVisible({ timeout: 10_000 });
  await expect(samPage.getByRole('status').filter({ hasText: 'Ada Admin is editing this image' })).toBeVisible();

  // Sam cannot draw on it.
  const stage = samPage.getByRole('application', { name: 'Annotation canvas' });
  const box = await stage.boundingBox();
  if (!box) throw new Error('no canvas');
  await samPage.keyboard.press('b');
  await samPage.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.4);
  await samPage.mouse.down();
  await samPage.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.6, { steps: 4 });
  await samPage.mouse.up();
  await samPage.waitForTimeout(1200);
  const images = await (await samPage.request.get('/api/v1/projects/' + projectUrl.split('/p/')[1] + '/images')).json();
  expect(images.items[0].annotation_count).toBe(0);

  // Ada can label the same image.
  await page.keyboard.press('b');
  const adaBox = await page.getByRole('application', { name: 'Annotation canvas' }).boundingBox();
  if (!adaBox) throw new Error('no canvas');
  await page.mouse.move(adaBox.x + adaBox.width * 0.4, adaBox.y + adaBox.height * 0.4);
  await page.mouse.down();
  await page.mouse.move(adaBox.x + adaBox.width * 0.6, adaBox.y + adaBox.height * 0.6, { steps: 4 });
  await page.mouse.up();
  await expect(page.getByRole('button', { name: 'Save status: Saved' })).toBeVisible({ timeout: 10_000 });

  // Sam's screen picks the change up without a reload.
  await expect(samPage.getByText('1 shape', { exact: true }).first()).toBeVisible({ timeout: 10_000 });
  await sam.close();
});

test('signing in with the wrong password says so', async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto('/');
  await page.getByLabel('Email').fill('admin@example.com');
  await page.getByLabel('Password').fill('not the password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toContainText('do not match');
  await context.close();
});
