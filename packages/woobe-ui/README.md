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
- `SectionBlock`, `TechnicalListItem` and `EmptyStatePanel` are shared presentation compositions.
- `RuntimeAssetCard`, `NetworkGraphInspector` and Knowledge build workflows are feature components.

Do not move a component into `woobe-ui` merely because it is visually complex. It belongs here only when it is presentation-only, domain-agnostic and has demonstrated reuse. Domain concepts such as Agent, Network, Run, Knowledge Collection, Release or Tool must not leak into this package.

## Primitives and shared compositions

Current reusable surface includes primitives and compositions such as:

- Button
- Input
- Textarea
- Select
- Field
- Alert
- Badge
- Card
- Dialog
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

The Control Plane dialog grammar is derived from the operational density used by ChatSurface Details. Features may change the content composition, but they must not create an independent modal design language.

Use `Dialog` as the shell and keep the shared header, border, radius, typography, controls, internal scrolling and footer treatment. Dialog copy stays on the Woobe product/system type scale; a larger modal is not a reason to enlarge typography.

Use the variants by intent:

- `standard`: confirmations, small forms, secret reveals and bounded actions. It remains compact, but uses the same typography, borders, controls and footer grammar as larger dialogs.
- `workspace`: configuration flows, inspectors and multi-step operational surfaces. It uses `max-w-dialog-wide` and `h-dialog-workspace`, keeps header/footer fixed, and gives scrolling to the content region.

The canonical workspace geometry is `68.75rem` maximum width and `min(56.25rem, calc(100svh - 2rem))` height. Features should not locally shrink or enlarge this shell with arbitrary `max-w-*` or viewport-height values unless the geometry is genuinely intrinsic to the feature.

Internal navigation remains feature-dependent. A settings surface may use a sidebar, while a creation workflow may use a stepper. The reusable contract is the shell, density, hierarchy and control language, not forcing unrelated workflows into the same navigation structure.

## Semantic Tailwind contract

The frontend consumes `woobe-ui/tailwind-preset`. Prefer semantic aliases over arbitrary values.

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

- Canvas: `#020817`
- Surface: `#0f1729`
- Control surface: `#0b1220`
- Border: `#1e293b`
- Primary: `#3b82f6`
- Product typography: Inter
- Technical typography: JetBrains Mono, with Fira Code/monospace fallback
- Technical/small radius: `2px`
- Common controls: `3px`
- Cards and larger containers: `4px`
- Default control height: `34px`
- Compact control height: `30px`
- Segmented control height: `27px`

The visual hierarchy is border-driven rather than shadow-driven. Blue is reserved for primary actions, focus, selection and operationally meaningful state. Technical typography is intentionally prominent in navigation, labels, controls, metadata, IDs, metrics and operational UI, while Inter remains the default for longer product copy and user-entered content.

Subtle grid/ASCII influence may appear as secondary identity, but it must not turn product surfaces into terminal emulation or decorative marketing layouts.

## Review checklist

Before considering a migrated surface complete, verify that:

- the feature still owns behavior and domain semantics while `woobe-ui` owns reusable appearance;
- common controls, dialogs, sections, states and technical rows use the shared primitives/compositions when an equivalent exists;
- no new arbitrary type scale, common radius, semantic color, shared shell width, control height, shadow or layer was introduced locally;
- loading, error, empty, disabled and read-only states follow the same visual grammar as the happy path;
- nested overlays use the shared layer contract and preserve focus/Escape/body-lock behavior;
- the surface remains usable from compact/mobile widths through workstation and ultrawide widths;
- additional 2K/ultrawide space improves information composition instead of inflating text and controls;
- user-configurable appearance values are not accidentally replaced by Control Plane design tokens;
- feature-specific geometry that remains local has a concrete behavioral or domain reason.
