import { expect, test, type Browser, type BrowserContext, type Page } from '@playwright/test';
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

async function signIn(browser: Browser, email: string): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto('/');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
  return { context, page };
}

test('an administrator puts an existing account on a project from the projects list', async ({ browser }) => {
  const ada = await signIn(browser, 'admin@example.com');

  // An account made from Settings, on no project yet.
  await ada.page.goto('/settings');
  await ada.page.getByRole('navigation', { name: 'Settings sections' }).getByRole('button', { name: 'People' }).click();
  await ada.page.getByRole('button', { name: 'Add someone' }).click();
  await ada.page.getByLabel('Email').fill('bob@example.com');
  await ada.page.getByLabel('Name', { exact: true }).fill('Bob Okafor');
  await ada.page.getByRole('textbox', { name: 'Password' }).fill(PASSWORD);
  await ada.page.getByRole('button', { name: 'Create the account' }).click();
  await expect(ada.page.getByText('Bob Okafor can sign in now.')).toBeVisible();

  // From the projects list, without opening the project.
  await ada.page.goto('/');
  await ada.page.getByRole('button', { name: 'More actions for Team project' }).click();
  await ada.page.getByRole('button', { name: 'Team and access' }).click();
  const team = ada.page.getByRole('dialog', { name: 'Team' });
  await expect(ada.page).toHaveURL(/\/$/);
  await team.getByLabel('Search people to add').fill('bob');
  await team.getByLabel('Role for the people you add').selectOption('reviewer');
  await team.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(team.getByLabel('Role of Bob Okafor')).toHaveValue('reviewer');
  await team.getByRole('button', { name: 'Done' }).click();

  const bob = await signIn(browser, 'bob@example.com');
  await expect(bob.page.getByText('Team project')).toBeVisible();
  await bob.context.close();
  await ada.context.close();
});

test('a manager brings in annotators but cannot hand out ownership', async ({ browser }) => {
  const ada = await signIn(browser, 'admin@example.com');
  const projects = await (await ada.page.request.get('/api/v1/projects')).json();
  const pid = projects.find((p: { name: string }) => p.name === 'Team project').id;
  const mia = await ada.page.request.post('/api/v1/users', {
    data: { email: 'mia@example.com', name: 'Mia Chen', password: PASSWORD },
  });
  const miaId = (await mia.json()).id;
  await ada.page.request.put(`/api/v1/projects/${pid}/members/${miaId}`, { data: { role: 'manager' } });
  await ada.context.close();

  const manager = await signIn(browser, 'mia@example.com');
  await manager.page.getByRole('button', { name: 'More actions for Team project' }).click();
  await manager.page.getByRole('button', { name: 'Team and access' }).click();
  const team = manager.page.getByRole('dialog', { name: 'Team' });
  await expect(team.getByLabel('Role for the people you add').locator('option')).toHaveText([
    'Reviewer',
    'Annotator',
    'Viewer',
  ]);
  // Ada owns the project: a manager sees her role but cannot change it or remove her.
  await expect(team.getByLabel('Role of Ada Admin')).toHaveCount(0);
  await expect(team.getByRole('button', { name: 'Remove Ada Admin' })).toHaveCount(0);
  // Sam is an annotator, which is a manager's to change.
  await team.getByLabel('Role of Sam Rivera').selectOption('viewer');
  await expect(team.getByLabel('Role of Sam Rivera')).toHaveValue('viewer');
  await team.getByLabel('Role of Sam Rivera').selectOption('annotator');
  await expect(team.getByLabel('Role of Sam Rivera')).toHaveValue('annotator');
  await manager.context.close();
});

test('someone who already has an account joins through an invite link', async ({ browser }) => {
  const ada = await signIn(browser, 'admin@example.com');
  const made = await ada.page.request.post('/api/v1/projects', { data: { name: 'Second project' } });
  const pid = (await made.json()).id;
  const invite = await ada.page.request.post('/api/v1/invites', {
    data: { project_id: pid, role: 'annotator' },
  });
  const path = (await invite.json()).path;
  await ada.context.close();

  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(path);
  await page.getByRole('button', { name: 'Sign in to join' }).click();
  await page.getByLabel('Email').fill('bob@example.com');
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('button', { name: 'Join as Bob Okafor' }).click();
  await expect(page).toHaveURL(new RegExp(`/p/${pid}$`));
  await context.close();
});

test('an annotator is not offered importing, exporting or new classes', async ({ browser }) => {
  const sam = await signIn(browser, 'sam@example.com');
  await sam.page.getByText('Team project').click();
  await expect(sam.page.getByRole('application', { name: 'Annotation canvas' })).toBeVisible();
  await expect(sam.page.getByRole('button', { name: 'Import', exact: true })).toHaveCount(0);
  await expect(sam.page.getByRole('button', { name: 'Export', exact: true })).toHaveCount(0);
  await expect(sam.page.getByLabel('New class name')).toHaveCount(0);
  await sam.context.close();
});

test('someone who is not an administrator still gets their own settings and the credit', async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto('/');
  await page.getByLabel('Email').fill('sam@example.com');
  await page.getByLabel('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();

  await page.goto('/settings');
  await expect(page.getByText('Settings for the whole server are up to an administrator')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sharing' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Appearance' })).toBeVisible();
  await page.getByRole('button', { name: 'About' }).click();
  await expect(page.getByRole('link', { name: 'M. Abdullah K. Mughal (MergenEnBilge)' })).toBeVisible();
  await expect(page.getByText('Version')).toBeVisible();
  // Where the server keeps its files is for administrators only.
  await expect(page.getByText('Data folder')).toHaveCount(0);
  await context.close();
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
