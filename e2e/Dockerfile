FROM mcr.microsoft.com/playwright:v1.52.0-noble

WORKDIR /workspace/e2e

COPY e2e/package.json ./
RUN npm install --no-package-lock

COPY e2e/ ./

CMD ["npx", "playwright", "test", "--config", "playwright.config.ts"]
