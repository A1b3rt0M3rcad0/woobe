# Third-Party Notices

Woobe Core includes third-party software. Every third-party component remains governed by the original license terms supplied by its owner.

The Woobe Core Sustainable Use License does not replace, narrow or expand third-party licenses.

## Release artifact inventory

The `Container quality` workflow generates SPDX SBOMs for the exact Core container artifacts currently released by this repository:

- `woobe-api`
- `woobe-web`
- `woobe-chat-embed`

The workflow derives a `woobe-third-party-inventory` artifact from those SBOMs. The inventory records the source artifact, package name, package version, declared license and concluded license reported for each discovered component.

SBOM generation is evidence, not legal certification. Before any public release, the exact generated inventory must be reviewed against the original component license text and distribution form.

When a dependency requires attribution, preservation of copyright text, a copy of its license, source availability, a source offer or another distribution obligation, that requirement must be satisfied in the released artifact and reflected in this notice file when applicable.

## Enterprise

Enterprise implementation, when introduced, must maintain its own dependency and notice inventory for every artifact not already covered by the Core release inventory. Enterprise licensing does not override third-party licenses.

## Release gate

`docs/PUBLIC_RELEASE_CHECKLIST.md` is the publication gate. The release must not be represented as license-complete merely because automated inventory generation succeeds.

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
