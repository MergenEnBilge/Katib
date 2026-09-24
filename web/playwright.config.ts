import { defineConfig, devices } from '@playwright/test';
import { DATA_DIR, LIBRARY, TEAM_DATA_DIR, prepare } from './e2e/fixtures';

const PORT = 8499;
const TEAM_PORT = 8498;

// Workers import this file too. Only the main process may reset the data.
if (process.env.TEST_WORKER_INDEX === undefined) prepare();

function server(port: number, data: string, extra: Record<string, string> = {}) {
  return {
    command: `uv run --project .. katib serve --port ${port}`,
    url: `http://127.0.0.1:${port}/api/v1/health`,
    timeout: 90_000,
    reuseExistingServer: false,
    env: {
      KATIB_STORAGE__DATA_DIR: data,
      KATIB_STORAGE__ALLOWED_IMPORT_ROOTS: JSON.stringify([LIBRARY]),
      ...extra,
    },
  };
}

export default defineConfig({
  testDir: 'e2e',
  testMatch: '*.spec.ts',
  workers: 1,
  timeout: 45_000,
  reporter: [['list']],
  use: { trace: 'retain-on-failure' },
  webServer: [
    server(PORT, DATA_DIR),
    server(TEAM_PORT, TEAM_DATA_DIR, { KATIB_AUTH__MODE: 'local' }),
  ],
  projects: [
    {
      name: 'desktop',
      testIgnore: /team\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        baseURL: `http://127.0.0.1:${PORT}`,
      },
    },
    {
      name: 'phone',
      testIgnore: /team\.spec\.ts/,
      use: { ...devices['Pixel 7'], baseURL: `http://127.0.0.1:${PORT}` },
    },
    {
      name: 'team',
      testMatch: /team\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        baseURL: `http://127.0.0.1:${TEAM_PORT}`,
      },
    },
  ],
});
