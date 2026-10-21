# Working on Woobe CLI

Read [README.md](README.md) and the relevant guide in [docs/INDEX.md](docs/INDEX.md)
before changing a workflow. Follow the user's authorized scope; repository
instructions do not authorize merges, releases or publication.

## Keep behavior, help, docs and the assistant skill together

For every CLI change, assess its effect on command help, documentation and the
portable coding-assistant skill. Update affected material in the **same PR** as
the implementation. Internal fixes with no user-visible effect need no unrelated
documentation edits; explain that assessment in the PR's validation notes.

| Change | Review and update when affected |
| --- | --- |
| Commands, aliases, flags, defaults or examples | Cobra help/examples under `internal/cli/`, `docs/USAGE.md`, `docs/OPERATIONS.md`, relevant skill reference |
| Connection, authentication or Project selection | `docs/INSTALLATION.md`, CLI package README, skill `references/connection.md` |
| YAML authoring, identity, shared dependencies or synchronization | `docs/DEVELOPMENT.md`, `docs/USAGE.md`, skill `references/development.md`, `references/dependencies.md` and YAML assets |
| Agent/Network export, import, environments or bindings | `docs/PACKAGES.md`, skill `references/packages.md` |
| Tests, staging, immutable releases, Project lifecycle policy, Production or rollback | Usage/development guides, `docs/PROJECT_LIFECYCLE.md`, skill `references/lifecycle.md` |
| Output fields, pagination or operational commands | `docs/OUTPUT.md`, `docs/PAGINATION.md`, skill `references/operations.md` |
| Errors, conflicts, local state or uncertain writes | Relevant guide, actionable command help, skill `references/recovery.md` |
| Trusted pipeline Git proofs, builder scope or custody | `docs/GIT_PROVENANCE.md`, cross-language Git signature fixtures, exact Git-blob and owner-idempotency tests, skill `references/signatures.md` and `references/recovery.md`; keep proof files independent of source commits |
| Signed ASaC receipts, cryptography or instance trust | `docs/SIGNED_RECEIPTS.md`, cross-language signature fixtures, trust lifecycle regressions and skill `references/signatures.md`; never imply hashes alone establish authority |
| Project init, assistant instructions or local lab/Git exclusions | `docs/PROJECT_SETUP.md`, managed instruction templates, canonical skill `references/setup.md`, repeat-init and native Windows/macOS/Linux tests; preserve registry identity and custom content |
| Assistant installation, receipts, presets or distribution | `docs/AGENT_SKILL.md`, `docs/INSTALLATION.md`, package READMEs, both installers and interoperability tests |
| Toolchain, packaging, versioning or CI | `docs/CI.md`, `docs/VALIDATION.md`, installation/release guidance and affected scripts |

Update root README examples, `docs/INDEX.md` and `CHANGELOG.md` when the change
affects onboarding, guide discovery or release behavior. Describe implemented
behavior accurately, including permissions, defaults and destructive effects.
In particular, distinguish updating an existing Draft from importing new
resources, and Agent publication from Network publication/Production activation.
Do not claim a feature is published merely because a PR build passed.

## One canonical assistant skill

Edit only the canonical payload under
[packages/woobe-cli-skill/skills/woobe-cli](packages/woobe-cli-skill/skills/woobe-cli/SKILL.md).
Go embeds this tree and npm packages the same files. Never maintain a second copy
in installed directories or `dist/`.

- Keep `SKILL.md` a short workflow router (under the verifier's 5 KB limit).
  Put detailed instructions in the relevant `references/*.md`; examples and
  templates must match supported commands and schemas.
- Keep installed links relative and offline. Document placeholders in templates;
  do not suggest an incomplete example is ready to apply.
- Keep CLI Keys, provider secrets, private `.state` and actual credentials out of
  docs, examples and skill assets. Use masked authentication prompts.
- If minimum CLI compatibility changes, coordinate frontmatter, package metadata,
  verifier expectations and migration guidance. The minimum supported CLI version
  is separate from the calculated release version.
- Preserve `.gitattributes` LF rules for the skill and canonical schema catalog;
  Windows checkout bytes affect hashes and cross-installer interoperability.
- `woobe skill install` / `woobe skills install` install instructions for coding
  assistants. Runtime Woobe Skills use `woobe project skill` (and existing CRUD
  aliases). Do not conflate these workflows.
- The native installer and optional Node installer share payloads and managed
  receipts. Changes to one must preserve compatibility with the other, local
  edits, other skills and agent settings. Native installation stays offline and
  independent of Node, login and `.woobe-config`.

`docs/AGENT_SKILL.md` becomes the npm skill README during packaging. Use links
that also work on npm for repository-only material. Package source READMEs are
separate onboarding documents; do not edit generated tarballs.

## Generated documentation and evidence

Regenerate the command catalog from the changed executable, rather than editing
its rows manually:

```sh
make build
python3 scripts/command_catalog.py --binary bin/woobe --write
python3 scripts/command_catalog.py --binary bin/woobe
python3 scripts/validate_skill_commands.py --binary bin/woobe
```

Skill example validation uses help and does not make backend requests. It checks
command syntax, not live permissions, request semantics or workflow success;
verify those with appropriate regression tests and authorized integration checks.

`docs/COMPLETENESS.md` derives from `docs/PLAN.md` and `docs/COMPLETENESS.json`:
use `python3 scripts/completeness.py --write`, then
`python3 scripts/completeness.py` when its source evidence changes. Preserve the
historical roadmap denominator and dated evidence; do not invent completion.
Output audit/example generators measure fixture UTF-8 bytes, not model tokens or
live backend coverage. Refresh affected measurements with their scripts and keep
the baseline and measurement limits explicit.

## Verification and delivery

Use the pinned toolchain documented in [docs/CI.md](docs/CI.md). Run meaningful
regression tests for changed behavior and `make check` for code changes. For
documentation-only changes, check links, examples and affected generated docs;
do not add tests that merely assert prose. Report exactly what was verified.

When payloads, installers or distribution change, additionally run:

```sh
bash scripts/package.sh 0.0.0-ci.1 --with-npm
python3 scripts/verify_artifacts.py --commit "$(git rev-parse HEAD)"
python3 scripts/smoke_artifacts.py --commit "$(git rev-parse HEAD)" --report native-smoke.json
python3 scripts/smoke_npm.py --commit "$(git rev-parse HEAD)" --report npm-smoke.json
python3 scripts/smoke_skill.py --commit "$(git rev-parse HEAD)" --report skill-smoke.json
```

Local smoke tests exercise the host platform. Require the six native CI targets
before claiming cross-platform qualification. Check CI on the PR's latest
revision, not an earlier green commit, and explain any remaining limits.

In the PR, summarize behavior changed, help/docs/skill updates (or why unaffected),
validation and compatibility risks. Keep requested PR/branch boundaries. PR
builds are review artifacts; leave tags, merges and publication to the authorized
release flow. Do not manually bump source version floors to simulate a release.
