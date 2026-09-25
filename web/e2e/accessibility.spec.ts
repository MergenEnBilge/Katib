import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { connectLibrary } from './fixtures';

/** Fail with a readable list of what is wrong, not just a count. */
async function expectNoViolations(page: Page, where: string): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  const summary = results.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join('\n  ')}`,
  );
  expect.soft(summary, `Accessibility problems on ${where}`).toEqual([]);
}

async function createProject(page: Page, name: string): Promise<void> {
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(name);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
}

for (const scheme of ['light', 'dark'] as const) {
  test.describe(`${scheme} theme`, () => {
    test.use({ colorScheme: scheme });

    test('the project list, a workspace and its dialogs have no detectable problems', async ({ page }) => {
      await page.goto('/');
      await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
      await expectNoViolations(page, 'the project list');

      await page.getByRole('button', { name: 'New project' }).first().click();
      await expectNoViolations(page, 'the new project dialog');
      await page.keyboard.press('Escape');

      await page.getByRole('button', { name: 'Local workspace' }).click();
      await expectNoViolations(page, 'the workspaces dialog');
      await page.keyboard.press('Escape');

      await createProject(page, `A11y ${scheme} ${test.info().project.name} ${Date.now()}`);
      await expectNoViolations(page, 'an empty workspace');

      await page.getByRole('button', { name: 'Import images' }).last().click();
      await expectNoViolations(page, 'the import dialog');
      await connectLibrary(page);
      await expect(page.getByText('images added.')).toBeVisible();
      await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();

      const panel = page.getByRole('button', { name: 'Show classes and details' });
      if (await panel.isVisible()) await panel.click();
      await page.getByLabel('New class name').fill('car');
      await page.getByRole('button', { name: 'Add', exact: true }).click();
      await expect(page.getByRole('button', { name: /^car/ }).first()).toBeVisible();
      await expectNoViolations(page, 'a workspace with an image and a class');

      if (test.info().project.name === 'desktop') {
        await page.getByRole('button', { name: 'Class manager' }).click();
        await expectNoViolations(page, 'the class manager');
        await page.keyboard.press('Escape');
        await page.getByRole('button', { name: 'Keyboard shortcuts' }).click();
        await expectNoViolations(page, 'the shortcuts list');
        await page.keyboard.press('Escape');
        await page.getByRole('button', { name: 'Dataset health' }).click();
        await expectNoViolations(page, 'the dataset health window');
        await page.keyboard.press('Escape');
        await page.getByRole('button', { name: 'Pre-label with a model' }).click();
        await expectNoViolations(page, 'the pre-label window');
        await page.keyboard.press('Escape');
        await page.getByRole('button', { name: 'Class gallery' }).click();
        await expect(page).toHaveURL(/gallery$/);
        await expectNoViolations(page, 'the class gallery');
      }
    });
  });
}
