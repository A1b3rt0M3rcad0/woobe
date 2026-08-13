# Public edition integration boundary

This directory contains only public integration contracts used to compose external Woobe editions with Community/Core.

The files in this directory are Covered Software under the repository root `LICENSE.md`. They are part of Woobe Community and may be used under the same Community terms.

No proprietary Cloud or Enterprise implementation belongs in this directory. Implementing, importing or depending on these contracts does not grant any license or other rights to proprietary Woobe edition source code maintained outside this repository.

The intended dependency direction is one-way:

`external edition repository -> Woobe Community public contract`

Woobe Community must not import an external proprietary edition implementation.

`editions` intentionally remains a Python namespace package. Do not add `src/editions/__init__.py`; this allows a private repository to provide `editions.cloud` while Community provides `editions.contracts`.
