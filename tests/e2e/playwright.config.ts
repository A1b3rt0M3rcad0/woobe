import { defineConfig, devices } from '@playwright/test'

const externalBaseURL = process.env.PLAYWRIGHT_BASE_URL

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 7_500 },
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: process.env.CI
    ? [['line'], ['html', { outputFolder: 'playwright-report', open: 'never' }]]
    : 'list',
  use: {
    baseURL: externalBaseURL ?? 'http://127.0.0.1:4173',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : undefined,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: externalBaseURL
    ? undefined
    : [{
        command: 'npm --prefix ../../packages/woobe-frontend run build && npm --prefix ../../packages/woobe-frontend run preview -- --host 127.0.0.1 --port 4173',
        url: 'http://127.0.0.1:4173',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
        env: {
          ...process.env,
          VITE_API_URL: 'http://127.0.0.1:4173',
          VITE_CHAT_EMBED_URL: 'http://127.0.0.1:4181',
          VITE_WOOBE_EDITION: 'core',
        },
      }, {
        command: 'npm --prefix ../../packages/woobe-embed run build && python3 -m http.server 4181 --bind 127.0.0.1 --directory ../../packages/woobe-embed/dist',
        url: 'http://127.0.0.1:4181/preview.html',
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      }],
})
