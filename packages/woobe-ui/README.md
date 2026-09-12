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
- Border: `#1e293b`
- Primary: `#3b82f6`
- Product typography: Inter
- Technical typography: JetBrains Mono, with Fira Code/monospace fallback
- Reduced radii and explicit borders are preferred over floating, heavily rounded surfaces.
