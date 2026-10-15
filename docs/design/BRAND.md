# Woobe brand assets

The owner-supplied `woobe-design-kit-atualizado-download.zip` is installed intact in [woobe-ui/brand-kit](../../packages/woobe-ui/brand-kit/README.md). It contains 334 files: the brand variants, transparent PNG/ICO exports, 25 UI icons, 53 illustrative component samples, tokens, reference boards and source notes. Open [the supplied catalog](../../packages/woobe-ui/brand-kit/preview/index.html) locally to browse it. The archive contains no font binaries.

The source guide distinguishes the traced vector artwork from editable component interpretations and original raster references. Those distinctions remain in the imported files. [brand-kit-import.json](../../packages/woobe-ui/brand-kit-import.json) records the archive SHA-256 and actual hashes of every installed file. The supplied manifest predates 37 updated files; it is preserved unchanged, with the differences recorded in the import inventory.

## Product integration

`WoobeLogo` in `@woobe/ui` renders the supplied SVG symbol and outlined horizontal wordmark. Its default `auto` appearance selects the primary orange/black logo on light surfaces and orange/white on dark surfaces, including charcoal navigation. Explicit `light` and `dark` appearances are available for fixed surfaces. The `mark` variant uses the orange symbol. `decorative` hides redundant branding from assistive technology.

```tsx
<WoobeLogo className="h-8" />
<WoobeLogo variant="mark" decorative className="h-5" />
<WoobeLogo appearance="dark" />
```

The login, Workspace/Project sidebars, context header, onboarding and authentication loading surface use this shared component. SVG geometry, proportions and transparency remain unchanged. The wordmark is outlined artwork, so it does not depend on a locally installed serif font. Interface text continues to use Inter, Georgia editorial headings and JetBrains Mono technical values.

The frontend's public favicon, PNG fallbacks, Apple icon and 192/512 icons are byte-identical copies of the corresponding kit files. The browser manifest adds identity metadata while retaining browser display. Embed HTML references the shared symbol at build time; customer-configured ChatSurface appearance remains independent. Vite includes only referenced artwork in the runtime build, while the full kit remains available to developers.

The kit's component SVGs and HTML/CSS are reference samples, not replacements for working React controls. Its raw color stylesheet uses hex values with names that overlap operational RGB variables; it is not globally imported. The existing `woobe-ui` semantic theme, contrast, typography and interaction contracts remain authoritative for the product. The brand orange is `#FF5500`.

The name, symbols and wordmarks remain subject to [TRADEMARKS.md](../../TRADEMARKS.md), separately from the software licenses.
