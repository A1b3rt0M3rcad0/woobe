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

## Geometry and tokens

Canvas `#f3f1ed`; panel `#fffefd`; panel header/footer band `#f6f4f0`; ink `#242321`; muted `#6b6863`; separator `#d4d0c8`; control boundary `#8c867d`; graphic accent `#ff5500`; small accent text `#ad3900`. These application mappings incorporate the owner's requested stronger surface contrast; the original Guild skill tokens remain unchanged. Semantic success `#197542`, warning `#9b5700`, failure `#b42318`. Avatars 28–32px, radius 4–6px; badges 4px; controls 6px; panels 10px. Panel inset 18px, header 48px, row at least 40–48px, footer around 40px. Content drives height. Canonical short panel shadow follows `assets/tokens.css`.

Workspace selection and project navigation share a scoped charcoal rail (`#242321`) on desktop and in the mobile drawer. Current items combine a visible border, raised charcoal surface and orange inset marker; keyboard focus uses a contrasting peach outline. Portal dialogs retain their light product surface. Primary creation, save and execution actions use the existing charcoal button. The pending-configuration link now shares that presentation, while secondary refresh actions remain quiet. Primary catalog filters and the selected Overview All filter use charcoal with light labels and counts. Technical microinterface segments keep their subtler treatment.

Reference figure dimensions (224px AgentMini or 270px UsageCap) describe **illustrations**. Operational controls use the specification's comfortable sizes; the application does not gain decorative marketing stages, fictitious budget enforcement, or additional KPIs. Main workspace, graph and inspector widths retain their information requirements. On narrow viewports, layouts wrap or stack; bidimensional code/tables scroll regionally. No hidden document overflow is accepted as proof of reflow.

Inter and JetBrains Mono are real variable WOFF2 resources self-hosted by `woobe-ui`, including Latin Extended and OFL notices. CSS family tokens in `guild-tokens.css` are consumed by Tailwind and CodeMirror through `woobeTypography`; consumers do not repeat their stacks. The Georgia stack uses system fonts and the browser serif fallback; no proprietary Georgia files are distributed. `MathSurface` retains its existing mathematical styling independently of editorial title sizing. Browser evidence must establish declared, loaded **and rendered** families with CDP, including 400/500 and Portuguese glyphs. Screenshots use deterministic, explicitly synthetic API fixtures; runtime and permissions remain backend-owned.

## Coverage and evidence

See `coverage.json` for the source inventory and `../screenshots/README.md` for the rendered evidence and reproduction commands. The inventory includes redirects and unused compatibility files so they cannot silently count as rendered pages. The owner requested a reduced documentation set: only current screenshots of the 18 main pages at desktop, tablet and mobile widths. Shared primitives, open overlays, internal sections, scrolling and nested confirmations remain covered by browser tests, without committed auxiliary screenshots. Browser checks, visual inspection and backend integration are distinct evidence.

The typography correction, local Georgia installation, checksum provenance and browser glyph checks are documented in [FONTS.md](FONTS.md). The original Guild v2 skill files are unchanged.
