# Woobe E2E

Black-box end-to-end validation for the assembled Woobe product. These tests exercise deployable boundaries and external contracts rather than importing production Python internals.

E2E lives under `tests/` because it validates the assembled system; it is not a production package or distributable Woobe artifact.


The default `playwright.config.ts` runs controlled API fixtures against the built
frontend and independently built ChatSurface iframe. The frontend CI installs the pinned lockfile and Chromium, builds/serves
the frontend, then runs these regressions, including authoritative ASaC selection,
unknown/disabled environments and Runtime Key dialogs. These fixtures prove UI
behavior; they do not qualify external providers or customer Production.

Install dependencies in both `packages/woobe-frontend` and `packages/woobe-embed`
first. Then, from `tests/e2e`:

```sh
npm ci
npx playwright install --with-deps chromium
npx playwright test --config playwright.config.ts
```

`PLAYWRIGHT_BASE_URL` optionally points at an already built/served frontend;
`PLAYWRIGHT_EMBED_BASE_URL` selects an existing embed server (default port 4181).
When no external frontend is configured, the runner builds and serves both.
Set `WOOBE_CAPTURE_DOCS=1` to refresh the documented screenshots after assertions;
see [capture provenance and instructions](../../docs/screenshots/README.md).
The suite includes axe checks for the Overview and real ChatSurface iframe, and
keyboard/mobile regressions across 360–1920px.
`fullstack.config.ts` is the separate real-service product suite. Generated
`test-results/` and `playwright-report/` remain local evidence.
