# Guild v2 interface review

The Control Plane now uses the owner's Guild-inspired Enterprise UI v2 specification: warm neutral surfaces, technical JetBrains Mono hierarchy, Inter prose, small square identities, fine separators, bounded operational panels and restrained semantic accents. Sign-in uses the separate editorial serif role. Real variable fonts are self-hosted, including Portuguese glyphs and their OFL notices.

The package boundaries remain intact. `woobe-ui` owns shared tokens and presentation; `woobe-frontend` owns product composition and interactions; `woobe-embed` remains an independent build with customer-configurable appearance. The runtime client and backend contracts were not replaced. The local review entry imports real production components and is excluded from the production application entry.

## Coverage

[coverage.json](coverage.json) inventories 53 route declarations: 26 rendered page surfaces and 27 redirect/compatibility paths. Authenticated workspace/project operations, first-run setup, account/workspace/project settings, MCP callback, public authentication and missing-route screens have captures. Redirects have browser checks and do not inflate the page count.

All 42 shared component modules have isolated or direct-overlay evidence. The overlay registry covers 71 exported-component/variant cases; ten inline hosts exercise context-manager selection, execution strategy, contract descriptions, runtime context, Agent snapshot, HTTP routes, MCP tools, full Agent results, legacy conversion and the Network ASaC workbench. Ten additional page/nested cases capture MCP input bindings, document deletion, configuration-use approval/revocation, cost coverage, Skill version review and Agent selection and local-discard confirmations. RAG runtime settings, batch configuration and Skill create/import modes are included explicitly. The RAG form scrolls as a full workspace on mobile instead of leaving a tiny nested viewport. Each registered overlay and inline host has desktop, tablet and mobile evidence. CLI Key and Runtime Key creation, synthetic secret reveals, rotation/revocation confirmations, provider credential actions, Project switching and mobile navigation are also recorded.

The [capture index](../screenshots/v2/README.md) and [searchable gallery](../screenshots/v2/index.html) include long-dialog scroll sequences, internal sections and populated resource catalogs. The README uses a current production-build Overview capture. Unrouted compatibility page modules are listed separately; `NetworkPage` is reached through `NetworkWorkspaceRoute`, and `ToolsCreateDialog` through the Tool flows.

## Changes found through rendered review

- Technical names, panel titles and regular monetary values now render in JetBrains Mono; prose uses Inter. CDP confirms custom font glyphs instead of relying on CSS declarations.
- Resource cards use small square identity marks and separated technical footers. Overview metrics retain their existing meaning in bounded header/value/footer windows.
- The shared class merger now resolves width, height and radius utilities consistently; wide snapshot workspaces no longer inherit a conflicting narrow modal width.
- Modal shells share keyboard handling, nested focus and Escape/focus-return behavior. Configuration and ASaC local-discard prompts use the shared nested confirmation; cancelling preserves local edits and discarding does not modify saved backend data. JSON expansion reuses the shared dialog; duplicate JSON presentation was removed.
- Long expiration options and long dialog titles wrap without truncation. Context Manager selection stacks its catalog and details on mobile; Agent/Network version managers keep their header and footer actions visible. The Run stream responds to its actual container width beside an inspector, preserving readable names. Populated Network canvas and inspector stack below 1280px; view controls wrap, and composition metadata uses readable configuration fields instead of oversized metrics.
- ChatSurface live testing stacks the real iframe and Session metadata on narrow screens; a browser assertion checks they do not intersect.
- Unknown runtime state is explicit and disables unsafe toggles. Environment availability reads “Enabled” rather than implying an active stream. Running/queued/failure presentation uses distinct semantic states.
- Root navigation waits for authentication initialization, preserving existing sessions when opening `/`.
- Dot indicators represent existing cost shares and pricing coverage. Unknown and zero remain distinct, and displayed percentages are not changed by graphical clamping. No budget policy or new backend enforcement was introduced.

## Verification

The [machine-readable validation record](validation.json) identifies the implementation commit and the successful runs, including focused rechecks after the final Network layout adjustment.

| Check | Result |
| --- | --- |
| Frontend Vitest | 110 files, 643 tests passed |
| Frontend TypeScript and production Vite build | Passed |
| Independent embed unit suite | 25 tests passed |
| Independent embed typecheck and production build | Passed |
| Production-build browser suite | 105 tests passed; five Network/Agent workspace cases rerun after the final Network reflow |
| Production component/overlay browser suite | 252 tests passed |
| Frontend UUID architecture policy | 1 test passed |
| Source/evidence inventory | Generator verifies captures for every classified route, shared module and registered overlay; all Dialog/Drawer/Dropdown source files classified; PNG dimensions and SHA-256 hashes recorded |
| Knowledge graph | Updated after source changes |
| Patch whitespace | `git diff --check` passed |

Commands and browser prerequisites are in [screenshots/README.md](../screenshots/README.md). Vite retains its large-chunk warning; no new bundle-size policy is introduced. No lint script is configured in the frontend manifests; TypeScript is checked by the production build. CI now includes shared-UI path triggers and the component/overlay browser suite.

Visual inspection is separate from these assertions. The reference images for marketplace anatomy, usage attribution, permission rows, terminal windows and editorial authentication were opened and compared with rendered captures. Review included desktop component/overlay sheets, responsive page and overlay sheets, and full-size checks of the Overview, sign-in, usage, Run stream, populated Network canvas at three widths, snapshot workspaces, Runtime Key forms and embedded conversation. Corrections were recaptured. This records the review performed; it is not a claim of numerical “100% fidelity” or complete accessibility certification.

## Proven limits

Browser runs use synthetic API fixtures. They exercise the real UI, routing, forms, keyboard behavior, actual iframe and HTTP response handling, but do not validate a live backend deployment or external model provider. Automated axe checks cover selected resource pages, Overview and ChatSurface. The 320px viewport and enlarged root-text checks supplement the 390/768/1440px matrix; root-text enlargement is not a cross-browser zoom certification. Chromium 154.0.8037.57 produced the committed captures; CI uses Playwright's pinned browser.

This work remains on branch `feature/frontend-enterprise-redesign` in [PR #217](https://github.com/A1b3rt0M3rcad0/woobe/pull/217), without merge. HTTPS Git pushes work. The current cloud network policy rejects `api.github.com`, so PR-body editing and current remote check inspection through `gh` are blocked. The required domain is saved in the environment configuration draft for review; saving a draft does not apply or publish it. This committed review document supplies the change summary, inventory, screenshot paths and local results in the PR diff while that API operation is blocked.
