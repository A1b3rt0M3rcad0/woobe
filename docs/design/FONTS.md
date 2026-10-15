# Typography and development fonts

The Control Plane composes three roles from the supplied Guild v2 reference `12-home-hero-user.png` and the owner's typography correction:

| Role | Family | Application |
| --- | --- | --- |
| Interface | Inter, 400 / 500 | Default body, navigation, breadcrumbs, menus, buttons, form controls, explanations, feedback and conversation |
| Editorial | Georgia, 400 | Page introductions, Overview story sections, first-run introductions and authentication headlines |
| Technical | JetBrains Mono, 400 / 500 | Microinterface headers, short resource identities, numerical metrics, versions, IDs, timestamps, code, schema tables and execution evidence |

`woobe-ui/src/styles/guild-tokens.css` owns the family stacks. Tailwind and CodeMirror consume those tokens through `woobeTypography`. Technical content opts in; cards, resource shells and dialogs do not impose mono on their descendants. Shared `Field` preserves a technical label variant while explanations stay Inter. `MathSurface` retains its existing mathematical styling; editorial scale is applied only to the selected headings.

Inter and JetBrains Mono are the existing self-hosted, licensed variable WOFF2 resources. No new font files are shipped with the application.

## Georgia installation in this development environment

Georgia **2.05** is installed in `/home/agent/.local/share/fonts/woobe-georgia`, with its original Regular, Bold, Italic and Bold Italic files. The Microsoft Core Fonts EULA permits installation and use; the original installer and EULA are retained locally. The font is not committed to this repository or included in a product bundle.

The public mirror supplied the unchanged `georgi32.exe` package:

- Mirror: <https://github.com/pushcx/corefonts>.
- Independent checksum authority: Debian `msttcorefonts` **3.8.1**, downloaded from <https://deb.debian.org/debian/pool/contrib/m/msttcorefonts/>.
- Installer SHA-256: `2c2c7dcda6606ea5cf08918fb7cd3f3359e9e84338dc690013f20cd42e930301`.

| Original file | SHA-256 verified against Debian |
| --- | --- |
| Georgia.TTF | `7d0bb20c632bb59e81a0885f573bd2173f71f73204de9058feb68ce032227072` |
| Georgiab.TTF | `82d2fbadb88a8632d7f2e8ad50420c9fd2e7d3cbc0e90b04890213a711b34b93` |
| Georgiai.TTF | `1523f19bda6acca42c47c50da719a12dd34f85cc2606e6a5af15a7728b377b60` |
| Georgiaz.TTF | `c983e037d8e4e694dd0fb0ba2e625bca317d67a41da2dc81e46a374e53d0ec8a` |

The environment-local installer is `/workspace/.local/bin/install-woobe-georgia.py`; its verified cache and provenance are in `/workspace/.local/share/woobe-font-installer`. It extracts the CAB data without executing Windows code, checks the installer and all four font hashes, preserves the license, rebuilds Fontconfig and requires `fc-match Georgia` to return Georgia. The environment configuration draft records reusable installation and startup instructions. Saving that draft does not publish or apply a new environment snapshot.

On other development machines, install the genuine Georgia family through a licensed local installation or the distribution's Microsoft Core Fonts installer. Other browser clients still follow `Georgia, "Times New Roman", serif` if Georgia is unavailable. Installing a system font on the development machine does not install it on visitors' devices.

## Browser verification

`tests/e2e/tests/typography.spec.ts` inspects actual production page glyphs with Chromium CDP, including the serif page/section titles, Inter navigation/breadcrumbs/filters, mono technical header and numerical value, plus authentication headlines and form controls. `tests/e2e/review/gallery.spec.ts` checks production shared controls, technical tables, CodeMirror and the Portuguese Inter/JetBrains specimens.

`WOOBE_REQUIRE_GEORGIA=1` requires actual Georgia glyphs for the editorial probes in this installed environment. Without that flag, the tests record and distinguish the system serif fallback so CI can run on a machine without proprietary fonts. Inter and JetBrains Mono must always render from the real custom fonts. Computed CSS and `document.fonts.ready` are accompanied by `CSS.getPlatformFontsForNode`; neither CSS declaration nor a successful font check alone establishes the rendered family.

Current results are stored in [fonts/](fonts/) and summarized in [validation.json](validation.json). Font names, custom/local origin, glyph counts, sizes and weights are recorded separately from screenshots.
