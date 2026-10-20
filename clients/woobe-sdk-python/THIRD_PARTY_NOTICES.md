# Third-Party Notices

Woobe SDK is licensed under MIT, but third-party software keeps its own license.

## Runtime dependencies

The package currently declares these direct runtime dependencies in `pyproject.toml`:

- `httpx`;
- `pydantic`.

They are installed as independent packages and are not relicensed by Woobe SDK.

Transitive dependencies are selected by the Python package resolver and may vary by compatible version. Their applicable license texts and metadata remain authoritative for those packages.

## Development dependencies

Test, lint, build and publication tools are development dependencies and are not automatically part of the Woobe SDK wheel merely because contributors use them.

## Vendored or copied material

Do not vendor, copy or embed third-party source, assets, schemas, generated code or license-controlled material without reviewing provenance and obligations first.

If a release begins to bundle third-party material that requires attribution or notice distribution, update this file in the same change and ensure the required notices are included in built artifacts.

## Release verification

Before publication:

1. review new and changed dependencies;
2. inspect the built wheel and sdist for bundled third-party material;
3. preserve any required copyright/license notices;
4. confirm that package metadata does not imply third-party code is MIT when it is not.

This file is an inventory and release-control surface. It does not replace the original licenses supplied by third-party authors.
