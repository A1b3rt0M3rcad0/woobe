# Client sources for the Artifacts delivery

These are exact source snapshots for atomic implementation in the main Woobe
Draft PR. `SOURCES.json` records source repository, immutable commit, original
file SHA-256 digests and licensing metadata. The original repositories and their
histories are unchanged. Changes after import intentionally diverge from these
original digests; the manifest is provenance, not a generated current-state hash.

The Go workspace connects the CLI to the local Go SDK without changing either
module path. From `clients/woobe-cli`, use `make build`, `make check`. From
`clients/woobe-sdk-go`, run `go test -race ./...`; `GOWORK=off go test -race ./...`
also validates the SDK's standalone dependency contract. From
`clients/woobe-sdk-python`, create a separate Python 3.13 venv, install `.[dev]`,
then run pytest, Ruff, build and Twine. Public Python package identity stays
`woobe-sdk`, with imports from `woobe`.

Nested `.github/workflows` files are imported source evidence. GitHub does not
execute them from `clients/**`; the root client validation workflow tests without
publishing. No automatic mirror, release, tag, registry push or package upload is
configured. Separate repositories remain possible future distribution destinations,
subject to a subsequent decision.

Preserve original SDK MIT notices and client third-party attribution. CLI package
metadata currently says `UNLICENSED`, and the pinned upstream contains no root
license file. This snapshot does not assign a replacement license or establish
publication permission. Resolve that explicitly before any future distribution.

After modifying imported clients, read their own AGENTS.md and update affected
help, documentation and canonical assistant skill together with behavior.

The backend live-contract workflow builds two independently reviewed CLI pins in
`.ci/**`. Those builds use `GOWORK=off` so the root integration workspace cannot
substitute the current local SDK or reject a pinned checkout outside its members.
The source manifest stores each digest under `sha256`, separately from its path;
filenames containing `key` must not turn public source hashes into scanner false positives.
