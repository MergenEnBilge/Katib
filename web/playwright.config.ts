import { defineConfig, devices } from '@playwright/test';
import { DATA_DIR, LIBRARY, prepare } from './e2e/fixtures';

const PORT = 8499;

// Workers import this file too. Only the main process may reset the data.
if (process.env.TEST_WORKER_INDEX === undefined) prepare();

export default defineConfig({
  testDir: 'e2e',
  testMatch: '*.spec.ts',
  workers: 1,
  timeout: 45_000,
  reporter: [['list']],
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: 'retain-on-failure' },
  webServer: {
    command: `uv run --project .. katib serve --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/v1/health`,
    timeout: 90_000,
    reuseExistingServer: false,
    env: {
      KATIB_STORAGE__DATA_DIR: DATA_DIR,
      KATIB_STORAGE__ALLOWED_IMPORT_ROOTS: JSON.stringify([LIBRARY]),
    },
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'phone', use: { ...devices['Pixel 7'] } },
  ],
});
