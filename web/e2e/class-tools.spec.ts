import { expect, test, type Page } from '@playwright/test';
import { connectLibrary } from './fixtures';

const API = '/api/v1';

async function drawBox(page: Page, from: [number, number], to: [number, number]): Promise<void> {
  const stage = page.getByRole('application', { name: 'Annotation canvas' });
  const box = await stage.boundingBox();
  if (!box) throw new Error('canvas has no size');
  await page.mouse.move(box.x + box.width * from[0], box.y + box.height * from[1]);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * to[0], box.y + box.height * to[1], { steps: 4 });
  await page.mouse.up();
}

test('merge two classes, undo it, then clean up from the gallery', async ({ page, request }) => {
  test.skip(test.info().project.name === 'phone', 'The class manager is a desktop flow.');

  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Merge ${Date.now()}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);
  const projectId = page.url().split('/p/')[1] as string;

  await page.getByRole('button', { name: 'Import images' }).last().click();
  await connectLibrary(page);
  await expect(page.getByText('images added.')).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Done' }).click();

  for (const name of ['car', 'van']) {
    await page.getByLabel('New class name').fill(name);
    await page.getByRole('button', { name: 'Add', exact: true }).click();
    await expect(page.getByRole('button', { name: new RegExp(`^${name}`) }).first()).toBeVisible();
  }

  // van is the active class, so this box is a van.
  await page.keyboard.press('b');
  await drawBox(page, [0.3, 0.3], [0.6, 0.6]);
  await expect(page.getByRole('button', { name: 'Save status: Saved' })).toBeVisible({ timeout: 10_000 });
  const classes = async (): Promise<{ name: string; annotation_count: number }[]> =>
    (await request.get(`${API}/projects/${projectId}/classes`)).json();
  await expect.poll(async () => (await classes()).map((c) => c.name).join()).toBe('car,van');

  // Merge van into car with a preview first.
  await page.getByRole('button', { name: 'Class manager' }).click();
  const dialog = page.getByRole('dialog', { name: 'Class manager' });
  await dialog.getByRole('button', { name: /^van/ }).click();
  await dialog.getByRole('button', { name: 'Merge into...' }).click();
  await dialog.getByRole('radiogroup', { name: 'Merge into' }).getByText('car').click();
  await expect(dialog.getByText(/1 annotation on 1 image will be relabeled/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Merge 1 annotation' }).click();

  await expect.poll(async () => (await classes()).map((c) => c.name).join()).toBe('car');
  expect((await classes())[0]?.annotation_count).toBe(1);
  await dialog.getByRole('button', { name: 'Done' }).click();

  // Undo from the toast brings van back with its shape.
  await expect(page.getByText(/Merged .van. into .car./)).toBeVisible();
  await page.locator('[aria-live="polite"]').getByRole('button', { name: 'Undo' }).click();
  await expect.poll(async () => (await classes()).map((c) => c.name).join()).toBe('car,van');
  expect((await classes())[1]?.annotation_count).toBe(1);

  // The gallery lists the shape as a crop. Deleting it can also be undone.
  await page.getByRole('button', { name: 'Class gallery' }).click();
  await expect(page).toHaveURL(/\/gallery$/);
  const tile = page.getByRole('button', { name: /van in street1\.png/ });
  await expect(tile).toBeVisible();
  await tile.click();
  await page.getByRole('button', { name: 'Delete...' }).click();
  await expect(page.getByText(/delete 1 annotation on 1 image/i)).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Delete', exact: true }).click();
  await expect.poll(async () => (await classes()).map((c) => c.annotation_count).join()).toBe('0,0');
  await page.locator('[aria-live="polite"]').getByRole('button', { name: 'Undo' }).click();
  await expect.poll(async () => (await classes()).map((c) => c.annotation_count).join()).toBe('0,1');
});

test('the health panel opens and reports the dataset', async ({ page }) => {
  test.skip(test.info().project.name === 'phone', 'Health is reached from the desktop toolbar.');
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Health ${Date.now()}`);
  await page.getByRole('button', { name: 'Create project' }).click();
  await page.getByRole('button', { name: 'Dataset health' }).click();
  await expect(page.getByRole('dialog', { name: 'Dataset health' })).toBeVisible();
  await expect(page.getByText('0 images, 0 shapes.')).toBeVisible();
});
