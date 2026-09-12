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
- SectionBlock
- MetricTile
- TechnicalListItem
- EmptyStatePanel
- CodePanel

Components enter `woobe-ui` only when they are presentation-only and have demonstrated reuse. Domain components such as Agent Inspector, Run Inspector, Network Canvas, Knowledge workflows or Tool configuration remain in their feature packages and consume the visual grammar exposed here.

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
