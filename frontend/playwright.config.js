import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/browser', fullyParallel: false, workers: 1, timeout: 60000,
  use: { baseURL: process.env.E2E_FRONTEND || 'http://127.0.0.1:5174', browserName: 'chromium', channel: 'chrome', headless: true, viewport: { width: 1440, height: 1100 }, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
});
