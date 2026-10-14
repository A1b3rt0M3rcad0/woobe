import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './review', testMatch: '*.spec.ts', fullyParallel: true, timeout: 30_000,
  expect: { timeout: 8_000 }, workers: 1, retries: 0,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  use: { baseURL: 'http://127.0.0.1:4182', viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : undefined,
    screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  outputDir: 'review-results',
  webServer: [{ command: 'npm --prefix ../../packages/woobe-frontend run dev -- --host 127.0.0.1 --port 4182', url: 'http://127.0.0.1:4182/review.html', reuseExistingServer: false,
    env: { ...process.env, VITE_API_URL: 'http://127.0.0.1:4182', VITE_CHAT_EMBED_URL: 'http://127.0.0.1:4183', VITE_WOOBE_EDITION: 'core' } },
    {command:'npm --prefix ../../packages/woobe-embed run build -- --outDir /tmp/woobe-embed-review && python3 support/serve_embed.py --port 4183 --directory /tmp/woobe-embed-review',url:'http://127.0.0.1:4183/chat/v1/iframe.html',reuseExistingServer:false}],
})
