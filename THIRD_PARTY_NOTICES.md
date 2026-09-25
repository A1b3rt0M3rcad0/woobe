# Third-Party Notices

This notice applies to third-party components included in Woobe Core and in any Enterprise distribution, regardless of the directory, package or artifact in which they appear. Every third-party component remains governed by the original license terms supplied by its owner.

Neither the Core license in [LICENSE.md](LICENSE.md), the Enterprise license in [LICENSE_EE.md](LICENSE_EE.md), nor an Enterprise Production Authorization replaces, narrows or expands those third-party terms. Placing a third-party component under an Enterprise Covered Path does not make that component Woobe-licensed Enterprise Software.

Conversely, rights granted by a third-party license apply to that third-party material; they do not grant rights to commercially supply the Woobe platform, execute Woobe Enterprise functionality in production or use Woobe branding. Those rights remain governed by the applicable Woobe documents, including [TRADEMARKS.md](TRADEMARKS.md).

## Release artifact inventory

The [Container quality workflow](.github/workflows/containers.yml) generates SPDX SBOMs for these Core container build targets:

- `woobe-api`
- `woobe-workers`
- `woobe-web`
- `woobe-chat-embed`

The workflow derives `.test-artifacts/THIRD_PARTY_INVENTORY.md` from those SBOMs and uploads it as `woobe-third-party-inventory` on manual (`workflow_dispatch`) runs. The inventory records the source artifact, package name, package version, declared license and concluded license reported for each discovered component.

The component notices collected in this file do not constitute a complete dependency inventory. The exact source or binary distribution, including packages and container images, determines which third-party notices and other obligations must accompany it.

SBOM generation is evidence, not legal certification. Before any public release, the exact generated inventory must be reviewed against the original component license text and distribution form.

When a dependency requires attribution, preservation of copyright text, a copy of its license, source availability, a source offer or another distribution obligation, that requirement must be satisfied in the released artifact and reflected in this notice file when applicable.

## Enterprise

Every Enterprise distribution must account for the third-party components actually included in its artifacts. The current workflow inventories the Core container targets listed above; it does not establish coverage of an Enterprise artifact.

An existing inventory may be reused only where it covers the actual components, versions and distribution forms. Additional or different Enterprise artifacts require corresponding inventory and notice coverage. Applicable third-party distribution obligations remain in force even when Enterprise functionality is inactive or used only for development and testing.

## Release gate

[RELEASING.md](RELEASING.md) is the publication gate. The release must not be represented as license-complete merely because automated inventory generation succeeds.

## PyYAML

PyYAML 6.0.3 is used to parse Skill frontmatter. It is distributed under the MIT license; the original notice is reproduced below.

```text
Copyright (c) 2017-2021 Ingy döt Net
Copyright (c) 2006-2016 Kirill Simonov

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
