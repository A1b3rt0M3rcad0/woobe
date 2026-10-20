# CI and release validation

The `CLI` workflow runs on pull requests, `feat/**`/`docs/**` pushes, manual
requests and as the reusable validation gate for `Release CLI`.

| Job | Acceptance |
| --- | --- |
| `test` | Version floor for both npm packages, Python publication/recovery tests, Node installer tests, roadmap audit, Go formatting/modules/vet/race/coverage and bounded fuzzing; native build/discovery |
| `package` | Six OS/architecture archives plus `woobe-cli` and `woobe-cli-skill` npm tarballs, schemas/notices, exact source identity and SHA256SUMS/artifacts.json |
| `native-smoke` × six | Linux amd64/arm64, macOS Intel/arm64, Windows amd64/arm64: filesystem/checkpoint/credential tests, real-binary Agent/Network author checkpoints/exact checkout/comment-preserving rebase/resolved merge, native/standalone installer regressions and receipt interoperability, downloaded archive validation, real binary and both npm tarballs installed offline; every fenced skill CLI example checked against packaged help |
| `ci` | All three validation groups must succeed; failed/cancelled/skipped groups reject the stable aggregate gate |

Nine concrete jobs execute. The stable `ci` check can be required by repository
branch rules; the workflow does not change those rules. Permissions are read-only.
The native installer embeds the same reviewed files as npm and needs no Node/npm.
Both installers share managed receipts and never call Woobe, edit credentials or modify agent settings.
Preset command regression tests cover both `skill` and `skills` for all six
destinations, dry-run, exact payload bytes, repeat installation, status and removal.
Each packaged native executable additionally runs the project-local commands
`woobe skill install --agent codex` and `--agent codex-legacy` without a connection
or `--project-dir`, including both Windows architectures.
The installed npm CLI launcher also installs/removes both Codex presets offline,
so npm argument forwarding and the embedded payload are verified together.
Its tests cover managed update/removal, local edit protection, multi-target preflight,
links/hardlinks, receipts, locks, rollback and preservation of concurrent edits.

## Evidence and reproduction

`cli-validation` stores coverage/discovery; `woobe-distribution` stores six native
archives, both npm tarballs, SHA256SUMS and artifacts.json. Each native runner
uploads `native-smoke.json`, `npm-smoke.json` and `skill-smoke.json`. Uploads fail
when evidence is absent, with 90-day requested retention subject to GitHub policy.
PR packages use `0.0.0-ci.RUN.ATTEMPT` and the exact checked-out integration SHA;
these are review artifacts, not published releases.

```sh
make check
bash scripts/package.sh 0.0.0-ci.1 --with-npm
python3 scripts/verify_artifacts.py --commit "$(git rev-parse HEAD)"
python3 scripts/smoke_artifacts.py --commit "$(git rev-parse HEAD)" --report native-smoke.json
python3 scripts/smoke_npm.py --commit "$(git rev-parse HEAD)" --report npm-smoke.json
python3 scripts/smoke_skill.py --commit "$(git rev-parse HEAD)" --report skill-smoke.json
```

Use Go 1.27.1, Python 3, Node 24/npm 11.5.1 and GNU archive/checksum tools.
Smokes execute their host's actual target. Loopback fixtures and offline installer
checks do not certify arbitrary live Woobe permissions, provider execution or host
assistant skill discovery. Paired live backend evidence is maintained separately.

## Publication

Master pushes and explicit `v*` tags start `Release CLI`: resolve immutable source
and SemVer, reuse CI, build/test GHCR from validated Linux binaries, preflight and
publish GitHub/GHCR, then publish exact npm tarballs. Releases are serialized;
existing tags/assets cannot be overwritten and recovery cannot downgrade latest.
GitHub uses job-scoped GITHUB_TOKEN permissions; npm jobs use only OIDC with
`id-token: write`, Node 24/npm 11.5.1, and clear NODE_AUTH_TOKEN. They never read
NPM_TOKEN. Pull requests never publish, reserve tags or request npm credentials.

The existing `npm` job remains independent. `npm-skill` is gated by repository
variable `WOOBE_SKILL_NPM_PUBLISH=true`, initially disabled until the new npm name
is bootstrapped and its own `release.yml` Trusted Publisher configured. Its
validated tarball is included in GitHub Releases regardless of that variable.
See [installation/recovery](INSTALLATION.md) and the
[new package bootstrap](AGENT_SKILL.md#versioning-and-initial-npm-publication-owner-once).

## Pagination continuation evidence — 2026-10-05

The code revision `659baea23458380b84bc7059d2a544c9c06fc1f5` passed all six jobs in [CLI run 37385398090](https://github.com/A1b3rt0M3rcad0/woobe-cli/actions/runs/37385398090). Stored artifacts include six distribution targets, cli-validation and native smoke reports from Linux/macOS/Windows, including body pagination and partial collection checks.

[Woobe PR #177](https://github.com/A1b3rt0M3rcad0/woobe/pull/177) pins that code revision. Its required live CLI workflow passed at backend `8ab9d13953c1cd77462af85a3a3a957395141edc`; other backend workflow results and user approval remain recorded in the PR. The backend pin can remain on the reviewed code revision when a later client commit only updates documentation/evidence.

Request-validation continuation adds loopback native checks for request direction, UUID/date-time and mutation refusal. These are client/package evidence; live server DTO validation remains a separate backend contract.

## Unified delivery

See [Deployment](DEPLOYMENT.md) for exact Release/Staging/local delivery, private intent recovery and explicit rollback. See [CI deployment](CI_DEPLOYMENT.md) for deploy-only authority and encrypted checkpoints. Existing commands retain their semantics.
