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
