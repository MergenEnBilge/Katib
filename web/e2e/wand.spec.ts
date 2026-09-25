import { expect, test } from '@playwright/test';
import { connectLibrary } from './fixtures';

const API = '/api/v1';

test('the magic wand outlines the bright square in a test picture', async ({ page, request }) => {
  test.skip(test.info().project.name === 'phone', 'Drawing precision is a desktop flow.');

  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Wand ${Date.now()}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  const projectId = page.url().split('/p/')[1] as string;

  await page.getByRole('button', { name: 'Import images' }).last().click();
  await connectLibrary(page);
  await expect(page.getByText('images added.')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();

  await page.getByLabel('New class name').fill('sign');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.getByRole('button', { name: /^sign/ }).first()).toBeVisible();

  await page.keyboard.press('w');
  const canvas = await page.getByRole('application', { name: 'Annotation canvas' }).boundingBox();
  if (!canvas) throw new Error('canvas has no size');
  // The picture sits in the middle of the canvas. Its bright square is at the picture's center.
  await page.mouse.move(canvas.x + canvas.width / 2, canvas.y + canvas.height / 2, { steps: 3 });
  await page.mouse.click(canvas.x + canvas.width / 2, canvas.y + canvas.height / 2);

  await expect(page.getByRole('button', { name: 'Save status: Saved' })).toBeVisible({ timeout: 10_000 });
  const images = (await (await request.get(`${API}/projects/${projectId}/images`)).json()) as { items: { id: string }[] };
  const saved = (await (await request.get(`${API}/images/${images.items[0]?.id}/annotations`)).json()) as {
    type: string;
    geometry: { points: [number, number][] };
  }[];
  expect(saved).toHaveLength(1);
  expect(saved[0]?.type).toBe('polygon');
  const xs = saved[0]?.geometry.points.map((p) => p[0]) ?? [];
  // The test picture's bright square covers the middle third.
  expect(Math.min(...xs)).toBeGreaterThan(0.3);
  expect(Math.max(...xs)).toBeLessThan(0.7);
});
