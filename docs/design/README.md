# Woobe visual contract · Guild-inspired v2

The repository owner's `guild-inspired-enterprise-ui-v2.zip` is the visual specification for this revision. This is an independent reconstruction language; no claim is made about Guild's internal tokens or original font files. External reference images are review inputs, never product screenshots.

## Modes and anatomy

The Control Plane, setup, configuration, authentication forms and ChatSurface controls use **operational / comfortable** density. Inter is the default for navigation, breadcrumbs, controls, forms, feedback and explanations. Georgia / Times New Roman / serif supplies regular editorial page titles and overview section headings. JetBrains Mono is explicit on technical panel headers, resource identifiers, table data, rules, status, timestamps and numerical values. A technical card or dialog does not impose monospace on its whole subtree. Primary technical titles use 500, values use 400, regular body is 14/20px, metadata is 12/18px. No operational panel is scaled as a marketing illustration.

| Family | Primary reference from skill | Applied anatomy |
| --- | --- | --- |
| Agent inventory and resource catalogs | `08-agent-marketplace.png` | AgentCatalogCard: small square identity, mono name, brief description, divided technical footer; 280–360px where space allows |
| Activity and resource lists | `05-mint-ui-overlap.png` | AgentStatusList: aligned rows, shared separators, explicit state, drill-down |
| Financial summaries and usage | `13-usage-cap-overlap-user.png` | SpendBreakdown / RunCost: compact header, scope/period, regular mono value, aligned attribution, footer; no invented caps or policy |
| Governance, access, configuration | `06-permission-matrix.png` | PermissionMatrix: labelled rows, real allowed/denied state, technical controls |
| API examples and CLI | `07-cli-workflow.png` | TerminalWindow: clear surface, mono output, bounded scrolling, copy confirmation |
| Editorial page titles, overview sections and sign-in narrative | `12-home-hero-user.png` | Editorial typography: regular Georgia heading, Inter explanation; usable form remains operational |
| Network graph and traces | `05-mint-ui-overlap.png` | Technical configuration and inspectable result in normal flow; Inter actions and explanations, mono execution data |

## Project Overview refinement

The Overview keeps the existing operational identity and package boundaries. Four compact primary metrics appear in order: Agent Runs, Network Runs, Agent Run Success, Runtime Cost. Network success and both average/p95 durations remain in Reliability & Performance. Inter carries Overview panel headings, labels, explanations and actions; Georgia carries editorial headings; JetBrains Mono carries numerical and technical evidence. This scoped refinement follows the owner's latest typography instruction.

Execution failures precede analytics and link to existing resources, recent error Runs when available, and the Run ledger. The ledger link is deliberately labelled as navigation to the ledger: that page does not currently accept URL filters. Only the API's existing Agent Run volume comparison is shown; success, duration and cost trends are not inferred.

Run Activity uses grouped bars at actual UTC bucket positions in the API's full half-open interval. Partial edge buckets are clipped to that interval. Missing buckets remain unavailable; explicit zeros remain zero. Agent, Network and error marks share their legend colors, and errors are labelled as a subset. A keyboard-accessible interval selector exposes the same evidence as pointer inspection. Summary totals retain their backend scope even when the time series is incomplete. No interpolation, cumulative area or synthetic data completion is used.

Success percentages retain the API's completed / terminal criterion, including cancelled Runs in the denominator and excluding running Runs. Absolute counts remain beside the percentages to contextualize small samples. Average and p95 use recorded terminal durations. Unpriced Run counts accompany partial cost subtotals. Configuration readiness distinguishes confirmed blockers, incomplete/unknown checks, paginated checks, permission failures and fetch failures; page-level completeness never becomes project readiness.

## Geometry and tokens

Canvas `#f3f1ed`; panel `#fffefd`; panel header/footer band `#f6f4f0`; ink `#242321`; muted `#6b6863`; separator `#d4d0c8`; control boundary `#8c867d`; graphic accent `#ff5500`; small accent text `#ad3900`. These application mappings incorporate the owner's requested stronger surface contrast; the original Guild skill tokens remain unchanged. Semantic success `#197542`, warning `#9b5700`, failure `#b42318`. Avatars 28–32px, radius 4–6px; badges 4px; controls 6px; panels 10px. Panel inset 18px, header 48px, row at least 40–48px, footer around 40px. Content drives height. Canonical short panel shadow follows `assets/tokens.css`.

Workspace selection and project navigation share a scoped charcoal rail (`#242321`) on desktop and in the mobile drawer. Current items combine a visible border, raised charcoal surface and orange inset marker; keyboard focus uses a contrasting peach outline. Portal dialogs retain their light product surface. Primary creation, save and execution actions use the existing charcoal button. A confirmed configuration blocker uses that primary presentation; unverified checks use a secondary review action, while refresh remains quiet. Primary catalog filters and the selected Overview All filter use charcoal with light labels and counts. Technical microinterface segments keep their subtler treatment.

Reference figure dimensions (224px AgentMini or 270px UsageCap) describe **illustrations**. Operational controls use the specification's comfortable sizes; the application does not gain decorative marketing stages, fictitious budget enforcement, or additional KPIs. Main workspace, graph and inspector widths retain their information requirements. On narrow viewports, layouts wrap or stack; bidimensional code/tables scroll regionally. No hidden document overflow is accepted as proof of reflow.

Inter and JetBrains Mono are real variable WOFF2 resources self-hosted by `woobe-ui`, including Latin Extended and OFL notices. CSS family tokens in `guild-tokens.css` are consumed by Tailwind and CodeMirror through `woobeTypography`; consumers do not repeat their stacks. The Georgia stack uses system fonts and the browser serif fallback; no proprietary Georgia files are distributed. `MathSurface` retains its existing mathematical styling independently of editorial title sizing. Browser evidence must establish declared, loaded **and rendered** families with CDP, including 400/500 and Portuguese glyphs. Screenshots use deterministic, explicitly synthetic API fixtures; runtime and permissions remain backend-owned.

## Coverage and evidence

See `coverage.json` for the source inventory and `../screenshots/README.md` for the rendered evidence and reproduction commands. The inventory includes redirects and unused compatibility files so they cannot silently count as rendered pages. The owner requested a reduced documentation set: only current screenshots of the 18 main pages at desktop, tablet and mobile widths. Shared primitives, open overlays, internal sections, scrolling and nested confirmations remain covered by browser tests, without committed auxiliary screenshots. Browser checks, visual inspection and backend integration are distinct evidence.

The typography correction, local Georgia installation, checksum provenance and browser glyph checks are documented in [FONTS.md](FONTS.md). The original Guild v2 skill files are unchanged.
