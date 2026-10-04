import { expect, test, type Page } from '@playwright/test';

const REVIEW = 'Katib runs on my laptop. The canvas is quick.';

async function openPanel(page: Page): Promise<void> {
  const toggle = page.getByRole('button', { name: 'Show classes and details' });
  if (await toggle.isVisible()) await toggle.click();
}

/** Select characters in the open document the way a mouse would, then let go. */
async function selectWords(page: Page, from: number, to: number): Promise<void> {
  await page.evaluate(
    ([start, end]) => {
      const words = document.querySelector('[data-testid="document-words"]');
      if (!words) throw new Error('the document is not on the page');
      // Each stretch of the document is one element with its first character's offset on it.
      const parts = [...words.querySelectorAll('[data-start]')];
      const find = (offset: number): [Node, number] => {
        for (const part of parts) {
          const base = Number((part as HTMLElement).dataset.start);
          const length = part.textContent?.length ?? 0;
          if (offset >= base && offset <= base + length) {
            return [part.firstChild as Node, offset - base];
          }
        }
        throw new Error(`offset ${offset} is not in the document`);
      };
      const range = document.createRange();
      const [startNode, startOffset] = find(start as number);
      const [endNode, endOffset] = find(end as number);
      range.setStart(startNode, startOffset);
      range.setEnd(endNode, endOffset);
      const selection = window.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
      window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
    },
    [from, to],
  );
}

test('label words in a text document, and keep them after a reload', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'New project' }).first().click();
  await page.getByLabel('Project name').fill(`Reviews ${test.info().project.name}`);
  // A text project: spans instead of the shapes a picture takes.
  await page.getByRole('checkbox', { name: /Boxes/ }).uncheck();
  await page.getByRole('checkbox', { name: /Polygons/ }).uncheck();
  await page.getByRole('checkbox', { name: /Text spans/ }).check();
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/p\/[0-9a-f-]{36}$/);

  // The rail asks for documents, not pictures.
  const dialog = page.getByRole('dialog');
  await page.getByRole('button', { name: 'Add documents' }).last().click();
  await dialog.getByLabel('Add documents').setInputFiles({
    name: 'review.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from(REVIEW, 'utf-8'),
  });
  await expect(dialog.getByText('1 document added.')).toBeVisible();
  await dialog.getByRole('button', { name: 'Done' }).click();

  // The words are shown, with no canvas in sight.
  await expect(page.getByTestId('document-words')).toContainText('Katib runs on my laptop.');
  await expect(page.getByRole('application', { name: 'Annotation canvas' })).not.toBeVisible();

  await openPanel(page);
  await page.getByLabel('New class name').fill('product');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.getByRole('button', { name: /product/ }).first()).toBeVisible();

  // Selecting the first word labels it, and the span is sent to the server.
  const saved = page.waitForResponse(
    (r) => r.url().includes('/annotations:batch') && r.request().method() === 'POST',
  );
  await selectWords(page, 0, 5);
  const list = page.getByRole('region', { name: 'Labelled spans' });
  await expect(list.getByRole('heading', { name: '1 span' })).toBeVisible();
  await expect(list.getByText('Katib', { exact: true })).toBeVisible();

  // It is still there after a reload, which means the server kept it.
  await saved;
  await page.reload();
  await expect(
    page.getByRole('region', { name: 'Labelled spans' }).getByRole('heading', { name: '1 span' }),
  ).toBeVisible();

  // And it can be taken off again.
  await page.getByRole('button', { name: /Remove this product span/ }).click();
  await expect(
    page.getByRole('region', { name: 'Labelled spans' }).getByRole('heading', { name: '0 spans' }),
  ).toBeVisible();
});
