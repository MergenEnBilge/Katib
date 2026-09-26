/**
 * Takes the pictures used in the README and the guide.
 *
 *   pnpm exec playwright test --config screenshots.config.ts
 *
 * It runs its own server on its own data folder, so it never touches the browser tests or anything
 * you are working on. The pictures land in docs/images.
 */
import { defineConfig, devices } from '@playwright/test';
import { mkdirSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';

const PORT = 8497;
const ROOT = resolve(import.meta.dirname, '.shots');
const DATA_DIR = join(ROOT, 'data');

export const OUT = resolve(import.meta.dirname, '..', 'docs', 'images');

if (process.env.TEST_WORKER_INDEX === undefined) {
  rmSync(ROOT, { recursive: true, force: true });
  mkdirSync(DATA_DIR, { recursive: true });
  mkdirSync(OUT, { recursive: true });
}

export default defineConfig({
  testDir: 'screenshots',
  testMatch: '*.ts',
  workers: 1,
  timeout: 120_000,
  reporter: [['list']],
  webServer: {
    command: `uv run --project .. katib serve --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/v1/health`,
    timeout: 90_000,
    reuseExistingServer: false,
    env: { KATIB_STORAGE__DATA_DIR: DATA_DIR },
  },
  projects: [
    {
      name: 'desktop',
      testIgnore: /phone\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        deviceScaleFactor: 2,
        baseURL: `http://127.0.0.1:${PORT}`,
      },
    },
    {
      name: 'phone',
      testMatch: /phone\.ts/,
      use: { ...devices['Pixel 7'], deviceScaleFactor: 2, baseURL: `http://127.0.0.1:${PORT}` },
    },
  ],
});
