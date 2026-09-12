# @woobe/ui

Reusable presentation layer for Woobe.

`woobe-ui` owns visual primitives, design tokens and shared composition rules. It is intentionally domain-agnostic: product screens, routing, authentication flows and feature behavior remain in `woobe-frontend`.

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

## Initial surface

The package starts with the primitives required by the authentication experience: Button, Input, Field, Alert, Badge and Card. Additional shadcn-derived primitives should only be incorporated when a real reusable use case appears.

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
- Typical compact control height: `34px`

The visual hierarchy is border-driven rather than shadow-driven. Blue is reserved for primary actions, focus, selection and operationally meaningful state. Technical typography is intentionally prominent in navigation, labels, controls, metadata, IDs, metrics and operational UI, while Inter remains the default for longer product copy and user-entered content.

Subtle grid/ASCII influence may appear as secondary identity, but it must not turn product surfaces into terminal emulation or decorative marketing layouts.
