# @woobe/ui

Reusable presentation layer and visual source of truth for Woobe.

`woobe-ui` owns visual primitives, design tokens, density rules and shared presentation compositions. It is intentionally domain-agnostic: product screens, routing, authentication flows, Agent/Network/Run semantics and feature behavior remain in `woobe-frontend`.

## Dependency direction

```text
shadcn/ui patterns
        ↓
Woobe-adapted primitives
        ↓
packages/woobe-ui
        ↓
packages/woobe-frontend
```

`woobe-ui` must never import from `woobe-frontend`.

## Ownership rule

Reusable visual decisions must originate in `woobe-ui`.

This includes:

- color palette and semantic colors;
- font families and semantic type scale;
- spacing scale and density;
- control heights and recurring icon sizes;
- radius;
- product breakpoints;
- structural widths used by shared shells;
- dialog/workspace dimensions;
- shadows;
- z-index/layers;
- reusable technical patterns such as the subtle grid;
- reusable primitives and presentation-only compositions.

`woobe-frontend` may keep feature-specific measurements when they are intrinsic to a domain component and have no reusable visual meaning. It should not introduce a new arbitrary font size, radius, control height, z-index, shared spacing rule or repeated shell dimension when an equivalent Woobe token exists.

Migrated feature code should import shared primitives directly from `@woobe/ui`. Local compatibility wrappers are migration infrastructure, not the default path for new or migrated feature code. A feature may compose primitives differently, but it should not locally resize or restyle a shared `Button`, `Input`, `Textarea`, `Select`, `Field`, `SectionBlock`, `Dialog`, `Stepper`, loading state or technical row to create a second visual contract.

The goal is not to remove every numeric value from feature code. The goal is to prevent feature code from becoming a second design system.

### Legitimate feature-owned geometry

A numeric or arbitrary value can remain in `woobe-frontend` when it is part of feature behavior or domain geometry rather than a reusable presentation rule. Typical examples include:

- Network Canvas node positions, handles, edge geometry and viewport calculations;
- Trace timelines and execution visualizations;
- split-pane calculations that depend on feature state;
- popover positioning calculations derived from an anchor and the viewport;
- upload/drop interaction geometry when it is unique to that interaction;
- domain limits such as timeouts, token budgets, depth, hops and invocation limits;
- user-configurable ChatSurface appearance values such as customer-selected colors, radius and spacing.

The syntax itself is not the violation. A repeated systemic visual decision without clear ownership is the violation.

## Component levels

Use three explicit levels of composition:

```text
primitive → shared presentation composition → feature component
```

Examples:

- `Button` is a primitive.
- `SectionBlock`, `TechnicalListItem`, `Stepper` and `EmptyStatePanel` are shared presentation compositions.
- `RuntimeAssetCard`, `NetworkGraphInspector` and Knowledge build workflows are feature components.

Do not move a component into `woobe-ui` merely because it is visually complex. It belongs here only when it is presentation-only, domain-agnostic and has demonstrated reuse. Domain concepts such as Agent, Network, Run, Knowledge Collection, Release or Tool must not leak into this package.

## Primitives and shared compositions

Current reusable surface includes primitives and compositions such as:

- Button
- Input
- InputGroup
- Textarea
- Select
- Field
- Alert
- Badge
- Card
- Dialog
- Stepper
- SegmentedControl
- Tabs
- PanelHeader
- PageHeader
- ResourcePage and resource page compositions
- SectionBlock
- MetricTile
- TechnicalListItem
- EmptyStatePanel
- LoadingState
- CodePanel
- JsonEditor
- JsonCodeBlock
- Operational ResourceCard / ResourcePill

The JSON editor surface, JSON formatting/validation helpers and CodeMirror visual theme live in this package together so `woobe-ui` never reaches back into `woobe-frontend` for implementation details.

Components enter `woobe-ui` only when they are presentation-only and have demonstrated reuse. Domain components such as Agent Inspector, Run Inspector, Network Canvas, Knowledge workflows or Tool configuration remain in their feature packages and consume the visual grammar exposed here.

## Dialog contract

The Control Plane dialog grammar is derived from the same operational density used by ChatSurface Details and the Project Overview reference. Features may change the content composition, but they must not create an independent modal design language.

Use `Dialog` as the shell and keep the shared header, border, radius, typography, controls, internal scrolling and footer treatment. Dialog copy stays on the Woobe product/system type scale; a larger modal is not a reason to enlarge typography.

Use the variants by intent:

- `standard`: confirmations, small forms, secret reveals and bounded actions. It remains compact, but uses the same typography, borders, controls and footer grammar as larger dialogs.
- `workspace`: configuration flows, inspectors and multi-step operational surfaces. It uses `max-w-dialog-wide` and `max-h-dialog`, while the content determines the actual height. Use `DialogContextBar`, `DialogBody` and `DialogFooter` when the feature needs fixed chrome with an independently scrolling body.

The canonical workspace width is `68.75rem` maximum. Height defaults to content-driven and is capped by `max-h-dialog`. Use `height="workspace"` when the design calls for a stable workspace across steps: `min(900px, calc(100svh - 32px))`, with a 16px viewport inset. Compose a flex child with `min-h-0 flex-1`, then `DialogContextBar`, `DialogBody` and `DialogFooter` to keep the context and actions outside the scrolling body. `DialogBody spacing="workspace"` follows the ChatSurface Details content insets (15px in constrained dialogs, up to 24px on desktop).

### Configuration hierarchy

Shared semantic type tokens own the hierarchy: 28px page titles, 15px section
headings, 14–16px product copy, 13px controls and 12px supporting metadata.
Technical microcopy has an 11px floor. Code, identifiers and structured evidence
use the mono family; ordinary labels and navigation use Inter.

Default controls are 40px high, compact controls 36px. Technical variants remain
available for dense workspaces. Touch layouts must keep primary actions reachable.
Use `Field`, `SectionBlock`, `ReadOnlyField`, `Stepper` and shared dialog layouts
without feature-local typography overrides.

Internal navigation remains feature-dependent. A settings surface may use a sidebar, while a creation workflow may use a stepper. The reusable contract is the density, hierarchy, spacing, typography and control language, not forcing unrelated workflows into the same geometry or navigation structure.

## Semantic Tailwind contract

The frontend consumes `woobe-ui/tailwind-preset`. Prefer semantic aliases over arbitrary values.

Font-size utility names are declared once in `woobeFontSizes` and consumed by both the Tailwind preset and `mergeWoobeClasses`. The shared `cn` helper and the frontend compatibility helper must use this configured merger. An unconfigured `twMerge` treats custom names such as `text-chrome-label` and `text-system-control` as colors, silently dropping either their size or their foreground color depending on class order. This can inflate controls to inherited body text even when their component source specifies the correct size.

Do not solve that collision by reordering classes, adding `!important`, or resizing individual features. Keep semantic font-size names registered in the shared `font-size` class group.

Examples:

```text
text-system-meta
text-system-label
text-system-control
text-system-heading
text-product-caption
text-product-small
text-product-body
text-heading
text-metric

p-ui-sm / p-ui-md / p-ui-lg
gap-ui-sm / gap-ui-md

h-control-xs
h-control-segment
h-control-sm
h-control
h-control-nav
h-control-row
h-panel-header
h-workspace-header

w-project-sidebar
w-playground-rail
w-operations-panel
w-inspector
w-inspector-expanded

max-w-resource
max-w-dialog
max-w-dialog-wide

shadow-popup
shadow-overlay

z-popover
z-playground-chrome
z-modal
z-nested-modal
z-focus
```

When a feature needs a recurring visual value that is not represented by the existing vocabulary, first decide whether it is truly feature-specific. If it is a reusable Woobe presentation rule, add it to this package and consume the token from the feature.

## Responsive contract

Responsive behavior is based on available viewport/container width, not the physical resolution or marketing name of a monitor.

Conceptually, Woobe should behave across these width classes:

- compact: below `640px`;
- mobile/large-mobile: `640–767px`;
- medium: `768–1023px`;
- desktop: `1024–1279px`;
- wide: `1280–1535px`;
- workstation: `1536–1919px`;
- ultrawide: `1920px` and above.

The exact implementation should use the product breakpoints exported by this package. These bands describe composition intent; they are not permission for features to create a second breakpoint system.

On workstation and ultrawide layouts, extra width should improve composition: persistent inspectors, wider data regions, useful columns, tables and contextual panels. Do not scale typography or common controls merely because more pixels are available.

## Visual foundations

The console uses a light editorial canvas and a dark navigation rail. The orbital
Woobe symbol and blue actions remain the product identity. The Guild-inspired
reference informs hierarchy and composition; no third-party branding or screenshots
are used in the distributed interface.

| Role | Value |
| --- | --- |
| Canvas | `#f7f7f4` |
| Surface | `#ffffff` |
| Control | `#f2f3f0` |
| Text | `#19231f` |
| Secondary text | `#626d68` |
| Border | `#d9deda` |
| Primary action | `#2459d3`, white label |
| Navigation | `#19231e`, light text |
| Success / warning / error | `#18734a` / `#946000` / `#b92f3c` |
| Network | `#7041cc` |

`src/styles/theme.css` owns the browser CSS variables and accessibility defaults.
`src/tokens/colors.ts` and the Tailwind preset expose their semantic roles. The
`.woobe-dark` scope is for navigation and editorial context, not a separate product
or a user theme setting. Existing slate utility aliases resolve through these
roles while features migrate to semantic names. `foreground` means readable text;
`primary-foreground` is the white label on a filled action.

Use 4px technical corners, 6px controls and 8px containers. Borders separate
ordinary surfaces; shadows belong to floating menus and dialogs. Technical grids
are secondary texture and must never reduce content contrast. Metrics retain
units, period, attribution and unknown states from API data.

ChatSurface remains in `woobe-embed` with its independent appearance configuration.
Console tokens must not override a customer's configured embed theme or sizing.

See [browser screenshots](../../docs/screenshots/README.md) for rendered examples
and the repeatable capture command.

## Review checklist

Before considering a migrated surface complete, verify that:

- the feature still owns behavior and domain semantics while `woobe-ui` owns reusable appearance;
- migrated code imports shared primitives directly from `@woobe/ui` unless a legacy compatibility boundary is explicitly required;
- common controls, dialogs, sections, states and technical rows use the shared primitives/compositions when an equivalent exists;
- no local feature override changes the canonical font size, control height, shared radius or recurring spacing of an imported primitive;
- no new arbitrary type scale, common radius, semantic color, shared shell width, control height, shadow or layer was introduced locally;
- loading, error, empty, disabled and read-only states follow the same visual grammar as the happy path;
- nested overlays use the shared layer contract and preserve focus/Escape/body-lock behavior;
- the surface remains usable from compact/mobile widths through workstation and ultrawide widths;
- additional 2K/ultrawide space improves information composition instead of inflating text and controls;
- user-configurable appearance values are not accidentally replaced by Control Plane design tokens;
- feature-specific geometry that remains local has a concrete behavioral or domain reason.
