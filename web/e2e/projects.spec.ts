import { expect, test } from '@playwright/test';

test('delete a project from its card, without opening it', async ({ page }) => {
  const name = `Trash ${test.info().project.name}`;
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(name);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  await page.getByRole('button', { name: 'Back to projects' }).click();
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();

  await page.getByRole('button', { name: `More actions for ${name}` }).click();
  const dialog = page.getByRole('dialog', { name });
  const confirm = dialog.getByRole('button', { name: 'Delete project' });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel(`Type "${name}" to confirm`).fill(name);
  await confirm.click();

  await expect(dialog).toBeHidden();
  await expect(page.getByText(name)).toBeHidden();
});

test('a card menu opens its project, and has no team to manage while accounts are off', async ({ page }) => {
  const name = `Handoff ${test.info().project.name}`;
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(name);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  const projectUrl = page.url();

  await page.getByRole('button', { name: 'Back to projects' }).click();
  await page.getByRole('button', { name: `More actions for ${name}` }).click();
  const menu = page.getByRole('dialog', { name });
  await expect(menu.getByRole('button', { name: 'Team and access' })).toHaveCount(0);
  await menu.getByRole('button', { name: 'Open project' }).click();
  await expect(page).toHaveURL(projectUrl);
});

test('the new project dialog asks what you are labelling before how', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  const dialog = page.getByRole('dialog');

  // Pictures to begin with, and only picture jobs are offered.
  await expect(dialog.getByRole('radio', { name: /^Pictures/ })).toHaveAttribute(
    'aria-checked',
    'true',
  );
  await expect(dialog.getByRole('radio', { name: /^Find objects/ })).toBeVisible();
  await expect(dialog.getByRole('radio', { name: /^Find things in the words/ })).toBeHidden();

  // Text instead, and the picture jobs give way to the text ones.
  await dialog.getByRole('radio', { name: /^Text/ }).click();
  await expect(dialog.getByRole('radio', { name: /^Find things in the words/ })).toBeVisible();
  await expect(dialog.getByRole('radio', { name: /^Find objects/ })).toBeHidden();

  // Choosing the shapes by hand offers only the ones that make sense for text.
  await dialog.getByRole('radio', { name: /^Choose the shapes myself/ }).click();
  await expect(dialog.getByRole('checkbox', { name: /^Spans/ })).toBeVisible();
  await expect(dialog.getByRole('checkbox', { name: /^Boxes/ })).toBeHidden();

  await dialog.getByRole('radio', { name: /^Sort documents/ }).click();
  await page.getByLabel('Project name').fill(`Sorting ${Date.now()}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  // A project of text holds documents, so that is what it asks for.
  await expect(page.getByRole('button', { name: 'Add documents' }).last()).toBeVisible();
});
