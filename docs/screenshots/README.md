# Woobe browser evidence · Guild v2

These screenshots show the implemented interface in Chromium, using deterministic **synthetic API fixtures**. They contain no production accounts, provider calls or real secret material. The fixtures' reference dates are part of the displayed data, not capture timestamps. The visual contract is [Guild v2, operational / comfortable](../design/README.md).

![Project Overview rendered from the production build](project-overview.png)

The [complete inventory](v2/README.md) links every routed page, shared component group, open overlay and secondary confirmation. The [searchable thumbnail gallery](v2/index.html) helps compare widths and states. [coverage.json](../design/coverage.json) records source paths, image dimensions and SHA-256 hashes; [REVIEW.md](../design/REVIEW.md) separates technical checks from visual inspection and backend integration.

## What the images represent

| Evidence | Method |
| --- | --- |
| `v2/pages/` | Actual production frontend build, navigated through the real router; 1440, 768 and 390px; public sign-in, first-owner registration and missing-route pages include mobile documents |
| `v2/components/` | Production `@woobe/ui` implementations in an isolated development review entry; typography, buttons, fields, badges, panels, tables, dates, feedback, code, menus and scrolling |
| `v2/overlays/` | Actual product dialogs/drawers/popovers, with real providers and API fixtures; open at desktop/tablet/mobile; section and scroll captures expose the rest of long content |
| `v2/flows/` | Creation, credential details, archive/revoke/rotation confirmations, Runtime Key and CLI Key synthetic reveals, Project switcher, mobile navigation and Agent inventory loading/empty/error |
| `v2/states/` | Hover, visible keyboard focus, selected tabs, copy success, invalid sign-in form, unavailable runtime, nested confirmation and compact/enlarged-text checks |
| `v2/fonts.json` | Chromium CDP identifies the **rendered custom font and glyph count**, alongside computed family, weight and size; probes include Portuguese glyphs |
| `chat-surface.png` | Independently built `woobe-embed`, with a completed fixture conversation |

The overlay review entry imports the production component implementations; it is not included in the application build. Its caption identifies the synthetic fixture. The ChatSurface live-test overlay embeds the real independently built iframe through its versioned `/chat/v1/` path.

Long operational dialogs deliberately retain their scrolling regions. A `390px.png` is the initial viewport; `390px-scroll-…` files show subsequent content with overlap for continuity. `section-…` files show internal navigation; `…-pan-…` files show horizontally scrollable navigation in sequence. This preserves real behavior without resizing the dialog into a nonfunctional mockup. Horizontal code and bidimensional canvas regions retain regional scrolling. Public documents use full-page captures where appropriate.

The root images remain convenient stable links for the README and product documentation:

| Area | Images |
| --- | --- |
| Operations | [Overview](project-overview.png), [Agents](agents.png), [Networks](networks.png), [Runs](traces.png), [Usage](usage.png) |
| Editing | [Agent creation](create-agent.png), [Agent playground](agent-playground.png), [Network workspace](network-workspace.png) |
| Resources | [Knowledge](knowledge.png), [Tools](tools.png), [Skills](skills.png), [Models](models.png), [Credentials](credentials.png) |
| Governance | [Environments](environments.png), [Runtime Keys](api-keys.png), [ChatSurfaces](chat-surfaces.png) |
| Access and delivery | [Sign-in](sign-in.png), [Mobile console](mobile-console.png), [ChatSurface](chat-surface.png) |

## Reproduce

From the repository root, install the locked dependencies:

```sh
npm --prefix packages/woobe-frontend ci
npm --prefix packages/woobe-embed ci
npm --prefix tests/e2e ci
cd tests/e2e
npx playwright install --with-deps chromium
WOOBE_CAPTURE_DOCS=1 npx playwright test --config playwright.config.ts
WOOBE_CAPTURE_DOCS=1 npx playwright test --config review.config.ts --workers=2
cd ../..
python3 scripts/frontend_visual_inventory.py
```

The browser configs start and stop the frontend and independent embed servers. Run the two suites sequentially when regenerating the same evidence directory. To inspect the gallery, serve `docs/screenshots/v2` with an ordinary static HTTP server and open `index.html` in a browser.

In this cloud environment the installed system Chromium is selected with `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium`. The main suite also uses `PLAYWRIGHT_BROWSERS_PATH=/workspace/.playwright` for its ffmpeg cache. CI installs Playwright's pinned Chromium instead. Browser differences can affect rasterization; the captures are review evidence, not cross-platform pixel baselines.

## Boundaries of validation

The browser suites exercise the real UI and HTTP contracts through fixtures. They do not demonstrate a running backend, live provider authorization or actual model execution. Automated axe checks cover selected Control Plane resources and ChatSurface; they are not a complete accessibility certification. Enlarging root text is a reflow stress check, not proof of browser zoom behavior across engines. Customer-selected ChatSurface appearance remains configurable.

Native browser `title` hints keep native rendering. There is no separate custom tooltip component to reproduce as a product overlay. Source inventory, successful browser assertions, rendered font evidence and visual review are recorded separately; none implies numerical “100% fidelity.”
