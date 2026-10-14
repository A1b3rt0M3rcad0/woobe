# Guild v2 interface and typography review

The typography correction restores three distinct roles: Inter is the interface default, Georgia regular carries editorial page titles and Overview sections, and JetBrains Mono remains explicit on technical panel headers, numerical metrics, resource identifiers, code, schemas, versions, timestamps and execution evidence. The primary reference is the supplied `12-home-hero-user.png`, with the operational microinterface anatomy retained from Guild v2. The original skill files are unchanged.

The structural fix removes global monospace inheritance from the frontend body, resource-page compatibility CSS, shared resource shell, cards and dialog subtrees. Tailwind and CodeMirror consume the existing CSS family tokens instead of repeating stacks. Shared buttons, fields, selects, navigation, tabs, feedback and descriptions use Inter; technical variants and technical tables retain mono. Local overrides were reviewed across Agent/Network workspaces, contracts, Knowledge, Tools, Skills, runtime references, credentials, keys, settings, first-run setup, authentication and conversation. Markdown prose and generated headings use Inter while code and schema tables remain mono. MathSurface keeps its mathematical styling independent of editorial sizing.

Georgia 2.05 was installed locally at the owner's request, with four original styles and verified Debian/MS Core Fonts checksums. It is a system font in this development environment, not a redistributed product font. Inter and JetBrains Mono remain the existing self-hosted variable WOFF2 resources. [FONTS.md](FONTS.md) records licensing, provenance and reproduction. Browser CDP confirms actual **Georgia** glyphs for editorial titles, custom **Inter** for navigation/controls/prose and custom **JetBrains Mono** for technical headers/values. The earlier Liberation Serif fallback is no longer the family used in these captures.

Package ownership is preserved: `woobe-ui` owns shared tokens and presentation, `woobe-frontend` owns application composition, and `woobe-embed` remains independently built with configurable appearance. Runtime and backend contracts are unchanged.

## Current screenshot scope

At the owner's request, the previous extensive screenshot gallery was removed. [The current index](../screenshots/README.md) contains only **18 main pages**, each at **1440, 768 and 390px**, for **54 freshly rendered images**. The root README uses the updated production-build Overview. Catalogs, usage and the Run ledger use populated synthetic fixtures; the Network workspace includes an actual graph node. Images show the initial viewport and preserve the application's real scrolling behavior.

The source inventory still covers routes, shared components, overlay sources and all non-test TSX modules. Removing component, modal and auxiliary-state images does not remove their browser checks. Optional detailed captures stay in ignored test output. [coverage.json](coverage.json) separates source/test inventory from the selected screenshot set and records image dimensions and hashes; explicit family-use counts are an audit aid, not proof of visual correctness.

## Validation

Exact commands, totals, implementation commit and capture metadata are recorded in [validation.json](validation.json). Verification includes frontend unit tests; the rebuilt production frontend with API-fixture browser tests; production shared-component and overlay browser tests at desktop/tablet/mobile widths; independent embed tests, typecheck and build; rendered-font probes; the screenshot inventory; and patch whitespace checks.

The font probes inspect declared family, weight and size alongside `CSS.getPlatformFontsForNode`, with actual glyph counts and custom/system origin. The production probes distinguish page/section headlines, navigation, breadcrumbs, filters, form controls, technical panels and numerical values. Shared-component probes include CodeMirror, technical tables and Portuguese text. The local strict run requires Georgia; CI may record its system-serif fallback while still requiring real Inter and JetBrains Mono webfonts.

Visual review compares the editorial-versus-technical hierarchy to the supplied Guild hero and microinterface references, then checks actual pages for wrapping, clipping, spacing and density. Browser tests cover forms, keyboard focus, nested confirmations, internal scrolling, responsive dialogs, unavailable states, regional canvas/table/code scrolling and the actual ChatSurface iframe. Text enlargement and 320px checks supplement the committed viewport matrix.

## Limits and delivery

The browser fixtures are synthetic. They qualify the real UI, routing and HTTP handling without establishing a running backend deployment or real model-provider authorization. Selected axe checks are not a complete accessibility certification. The system Chromium used locally can rasterize differently from CI's pinned Chromium. Georgia installed here does not install it on other clients; they follow the declared fallback stack. No numerical fidelity score is claimed.

All work stays on `feature/frontend-enterprise-redesign` in [PR #217](https://github.com/A1b3rt0M3rcad0/woobe/pull/217), without merge. HTTPS Git pushes work. The current cloud HTTP policy blocks `api.github.com`; the committed review provides the current change summary while PR-body updates and remote CI inspection through `gh` remain unavailable. Reusable environment installation/start instructions, including Georgia, were saved as a configuration draft; applying/publishing that draft is a separate environment-settings action.
