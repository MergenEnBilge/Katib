import { expect, test, type Page } from '@playwright/test';
import { connectLibrary } from './fixtures';

const API = '/api/v1';

async function canvasBox(page: Page) {
  const box = await page.getByRole('application', { name: 'Annotation canvas' }).boundingBox();
  if (!box) throw new Error('canvas has no size');
  return (x: number, y: number) => ({ x: box.x + box.width * x, y: box.y + box.height * y });
}

test('draw a rotated box, landmarks, a mask and a tag, and keep them after a reload', async ({ page, request }) => {
  test.skip(test.info().project.name === 'phone', 'Drawing precision is a desktop flow.');

  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Shapes ${Date.now()}`);
  for (const label of ['Rotated boxes', 'Keypoints', 'Brush masks', 'Image tags']) {
    await page.getByLabel(label).check();
  }
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  const projectId = page.url().split('/p/')[1] as string;

  await page.getByRole('button', { name: 'Import images' }).last().click();
  await connectLibrary(page);
  await expect(page.getByText('images added.')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();

  await page.getByLabel('New class name').fill('person');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.getByRole('button', { name: /^person/ }).first()).toBeVisible();

  // Landmarks belong to the class, so define them before drawing.
  await page.getByRole('button', { name: 'Class manager' }).click();
  const dialog = page.getByRole('dialog', { name: 'Class manager' });
  await dialog.getByRole('button', { name: /^person/ }).click();
  await dialog.getByLabel('Landmarks, one per line').fill('head\nhip\nfoot');
  await dialog.getByLabel('Lines between landmarks').fill('1-2, 2-3');
  await dialog.getByRole('button', { name: 'Save landmarks' }).click();
  await expect(dialog.getByLabel('Landmarks, one per line')).toHaveValue('head\nhip\nfoot');
  await dialog.getByRole('button', { name: 'Done' }).click();

  const at = await canvasBox(page);

  // Rotated box: drag along one edge, then move out and click for the width.
  await page.keyboard.press('o');
  await page.mouse.move(at(0.2, 0.5).x, at(0.2, 0.5).y);
  await page.mouse.down();
  await page.mouse.move(at(0.5, 0.45).x, at(0.5, 0.45).y, { steps: 4 });
  await page.mouse.up();
  await page.mouse.move(at(0.35, 0.7).x, at(0.35, 0.7).y, { steps: 3 });
  await page.mouse.down();
  await page.mouse.up();

  // Landmarks, placed in order.
  await page.keyboard.press('k');
  for (const [x, y] of [
    [0.7, 0.2],
    [0.7, 0.4],
    [0.7, 0.6],
  ] as const) {
    await page.mouse.click(at(x, y).x, at(x, y).y);
  }

  // A brush stroke. The image sits in the middle of the canvas, so stay well inside it.
  await page.keyboard.press('r');
  await page.mouse.move(at(0.1, 0.3).x, at(0.1, 0.3).y);
  await page.mouse.down();
  await page.mouse.move(at(0.3, 0.3).x, at(0.3, 0.3).y, { steps: 6 });
  await page.mouse.up();

  // A tag on the whole image.
  await page.getByRole('group', { name: 'Tags on this image' }).getByRole('button', { name: /person/ }).click();

  await expect(page.getByRole('button', { name: 'Save status: Saved' })).toBeVisible({ timeout: 10_000 });
  const images = (await (await request.get(`${API}/projects/${projectId}/images`)).json()) as { items: { id: string }[] };
  const imageId = images.items[0]?.id;
  const types = async (): Promise<string[]> =>
    ((await (await request.get(`${API}/images/${imageId}/annotations`)).json()) as { type: string }[])
      .map((a) => a.type)
      .sort();
  await expect.poll(types).toEqual(['keypoints', 'mask', 'obb', 'tag']);

  await page.reload();
  await expect(page.getByRole('application', { name: 'Annotation canvas' })).toBeVisible();
  await expect.poll(types).toEqual(['keypoints', 'mask', 'obb', 'tag']);
});
