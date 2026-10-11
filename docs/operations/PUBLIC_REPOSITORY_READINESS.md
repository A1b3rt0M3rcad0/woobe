# Preparing Woobe for a public repository

This is the publication gate for changing `A1b3rt0M3rcad0/woobe` from **private** to **public**. Woobe remains **Source-Available**, not Open Source. The Core, Enterprise and trademark boundaries are governed by `LICENSE.md`, `LICENSE_EE.md`, `LICENSING.md` and `TRADEMARKS.md`.

## Target CI

- All GitHub Actions jobs use `ubuntu-24.04` standard GitHub-hosted Linux x64 runners; no workflow targets `self-hosted`.
- Docker-intensive jobs use ephemeral, isolated VMs. CI does not depend on the maintainer's computer, custom runner labels or a shared Docker host lock.
- Release candidates still target `linux/amd64` and `linux/arm64` through pinned QEMU/Buildx actions. Distinct image builds run in parallel on separate VMs.
- Validation PRs receive read-only `GITHUB_TOKEN` permissions. Only trusted release workflows originating from `master` receive the narrowly required write permissions.
- Standard GitHub-hosted minutes are free in public repositories; the 14 GB runner disk remains constrained. Keep bounded timeouts and reclaim unused Docker images/cache between CI phases.

## Mandatory administrative and security checks before public visibility

1. **Historical secret and data review.** Audit every reachable Git history ref, release, PR discussion, Actions artifact and historical Actions log for committed passwords/tokens, internal-only code, customer data, personal information and private endpoints. The existing `Security audit` (Gitleaks) workflow is helpful, but successful scans do **not** establish that historical logs or unreachable Git objects are safe. Rotate/revoke any exposed credential before opening visibility. Deleting a file or rewriting a commit does not revoke a leaked key.
2. **License and provenance review.** Confirm the Core/Enterprise boundary, software and brand permissions, contributor CLA, third-party notices and distributable assets. `LICENSING.md` explicitly notes a qualified legal review gate. Public visibility does not turn Woobe into Open Source or relicense third-party materials.
3. **Remove personal runners.** Identify only runners registered to Woobe under **Settings → Actions → Runners**. Stop/uninstall their services on the actual host and remove their GitHub registrations; changing `runs-on` does not deregister them. An authorized administrator can inspect registrations with `gh api repos/A1b3rt0M3rcad0/woobe/actions/runners` and delete each verified repository runner with `gh api -X DELETE repos/A1b3rt0M3rcad0/woobe/actions/runners/RUNNER_ID`. Do not remove an organization runner or a runner used by another repository.
4. **GitHub Actions configuration.** Enable standard hosted runners and approvals for outside contributors where supported. Default workflow permissions to read, restricting writes to trusted release paths. To propagate bot-created release PR events, configure a scoped `WOOBE_RELEASE_TOKEN` (GitHub App token or fine-grained PAT) with only the needed permissions, or explicitly validate the default-token dispatch fallback. Allow Actions to create pull requests when using `GITHUB_TOKEN` for that purpose. Never expose release credentials to pull-request code.
5. **Protect `master` and release refs.** Enable branch protection/rulesets, prohibit direct pushes, require review, and configure required CI checks. Note that path-filtered workflows can be absent for unrelated PRs: do not configure an impossible required-check set. Keep the automatic release PR merge capability explicitly authorized **after** its exact-head CI gate passes. Restrict trusted workflow edits and immutable release tag creation.
6. **Security features.** Enable private vulnerability reporting, secret scanning/push protection where available, Dependabot alerts and code scanning. Verify the public security-disclosure contact, issue templates and contribution policy. GitHub also exposes existing Actions logs/history when changing a private repository to public.
7. **GHCR access.** Changing repository visibility does not automatically prove public access to linked container packages. Check the four GHCR packages `woobe-api`, `woobe-workers`, `woobe-frontend` and `woobe-embed` individually; mark public when intended and confirm anonymous image pulls for each immutable release digest.
8. **End-to-end CI and publication.** Run the eight required CI workflows on the exact PR SHA and validate tests, image security scans, multi-architecture images, smoke tests and digest promotion. PRs in Draft cannot be merged until marked ready. Confirm that the top-level `Release Woobe` workflow reaches a successful terminal state; do not bypass or manually force required gates.

## Safe sequence

1. Review the runner migration PR, allow GitHub-hosted jobs to complete and merge only when the checks pass.
2. De-register the personal runners and stop their services. Verify no job still selects a self-hosted label.
3. Complete historic-secrets/Actions-log and license reviews; set repository security, Actions policy and release permissions.
4. Change visibility to public only after the gate is satisfied. Making a repository private again does not erase copies or forks.
5. Check pending PR runs, GHCR package visibility and anonymous pulls. Confirm automatic releases remain reproducible.

**Do not merge this migration directly into `master` without reviewing its hosted CI results.** Woobe intentionally starts an automatic version/release transaction when an ordinary PR is merged into `master`, and the release orchestrator must not publish if required CI is missing or failing.

Official references: [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [Actions security](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions), [visibility changes](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility).
