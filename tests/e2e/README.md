# Woobe E2E

Black-box end-to-end validation for the assembled Woobe product. These tests exercise deployable boundaries and external contracts rather than importing production Python internals.

E2E lives under `tests/` because it validates the assembled system; it is not a production package or distributable Woobe artifact.


The default `playwright.config.ts` runs controlled API fixtures against the built
frontend. The frontend CI installs the pinned lockfile and Chromium, builds/serves
the frontend, then runs these regressions, including authoritative ASaC selection,
unknown/disabled environments and Runtime Key dialogs. These fixtures prove UI
behavior; they do not qualify external providers or customer Production.

From `tests/e2e`, after installing frontend dependencies:

```sh
npm ci
npx playwright install --with-deps chromium
VITE_CHAT_EMBED_URL=http://127.0.0.1:8081 npx playwright test --config playwright.config.ts
```

`PLAYWRIGHT_BASE_URL` optionally points at an already built/served frontend.
`fullstack.config.ts` is the separate real-service product suite. Generated
`test-results/` and `playwright-report/` remain local evidence.
