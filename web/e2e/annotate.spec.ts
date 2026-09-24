import { expect, test, type Page } from '@playwright/test';
import { LIBRARY } from './fixtures';

const API = '/api/v1';

async function openPanel(page: Page): Promise<void> {
  const toggle = page.getByRole('button', { name: 'Show classes and details' });
  if (await toggle.isVisible()) await toggle.click();
}

async function drawBox(page: Page, from: [number, number], to: [number, number]): Promise<void> {
  const stage = page.getByRole('application', { name: 'Annotation canvas' });
  const box = await stage.boundingBox();
  if (!box) throw new Error('canvas has no size');
  await page.mouse.move(box.x + box.width * from[0], box.y + box.height * from[1]);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * ((from[0] + to[0]) / 2), box.y + box.height * ((from[1] + to[1]) / 2));
  await page.mouse.move(box.x + box.width * to[0], box.y + box.height * to[1]);
  await page.mouse.up();
}

test('create a project, import images, label one and keep it after a reload', async ({ page, request }) => {
  const name = `Street ${test.info().project.name}`;

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(name);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  const projectId = page.url().split('/p/')[1] as string;

  // Import three images from the server folder.
  await page.getByRole('button', { name: 'Import images' }).last().click();
  await page.getByLabel('Folder on the Katib computer').fill(LIBRARY);
  await page.getByRole('button', { name: 'Import folder' }).click();
  await expect(page.getByText('3 images added.')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();

  // A class, then a box.
  await openPanel(page);
  await page.getByLabel('New class name').fill('car');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.getByRole('button', { name: /car/ }).first()).toBeVisible();
  if (await page.getByRole('button', { name: 'Show classes and details' }).isVisible()) {
    await page.getByRole('button', { name: 'Show classes and details' }).click();
  }

  await page.keyboard.press('b');
  await drawBox(page, [0.3, 0.3], [0.6, 0.6]);

  await expect(page.getByRole('button', { name: 'Save status: Saved' })).toBeVisible({ timeout: 10_000 });
  const images = (await (await request.get(`${API}/projects/${projectId}/images`)).json()) as {
    items: { id: string; annotation_count: number }[];
  };
  const first = images.items[0];
  expect(first).toBeDefined();
  const count = async (): Promise<number> => {
    const list = await (await request.get(`${API}/images/${first?.id}/annotations`)).json();
    return list.length;
  };
  const saved = await (await request.get(`${API}/images/${first?.id}/annotations`)).json();
  expect(saved).toHaveLength(1);
  expect(saved[0].type).toBe('box');

  // Still there after a reload.
  await page.reload();
  await expect(page.getByRole('application', { name: 'Annotation canvas' })).toBeVisible();
  await expect.poll(count).toBe(1);

  // Undo history is per session, so draw a second box after the reload and undo that one.
  await page.keyboard.press('b');
  // The canvas is taller than the image on a phone, so stay near the middle.
  await drawBox(page, [0.4, 0.46], [0.55, 0.54]);
  await expect(page.getByRole('button', { name: 'Save status: Saved' })).toBeVisible({ timeout: 10_000 });
  await expect.poll(count).toBe(2);
  await page.keyboard.press('Control+z');
  await expect.poll(count, { timeout: 10_000 }).toBe(1);
});

test('an empty project explains what to do first', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Empty ${test.info().project.name}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByText('Nothing to annotate yet')).toBeVisible();
});

test('a duplicate project name is refused with a clear message', async ({ page }) => {
  const name = `Dup ${test.info().project.name}`;
  await page.goto('/');
  for (let i = 0; i < 2; i++) {
    if (i === 1) await page.goto('/');
    await page.getByRole('button', { name: 'New project' }).first().click();
    await page.getByLabel('Project name').fill(name);
    await page.getByRole('button', { name: 'Create project' }).click();
  }
  await expect(page.getByRole('alert')).toContainText('already exists');
});
