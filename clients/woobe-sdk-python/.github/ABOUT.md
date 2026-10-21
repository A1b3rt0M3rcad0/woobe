# GitHub repository automation

`.github/` contains GitHub-specific repository metadata and automation for Woobe SDK.

Changes here can alter pull-request policy, CI behavior, issue intake, security checks, package publication and release mechanics even though this directory contains no SDK runtime code.

## Contents

- `workflows/ci.yml` — Python compatibility, lint, tests and package-build validation.
- `workflows/security.yml` — scheduled dependency vulnerability audit.
- `workflows/release.yml` — tag verification, package build, PyPI publication and GitHub Release creation.
- `ISSUE_TEMPLATE/` — structured bug and feature intake.
- `PULL_REQUEST_TEMPLATE.md` — canonical SDK pull-request checklist.
- `release.yml` — generated GitHub release-note categories.

CI should validate repository-owned contracts rather than define a second implementation of SDK semantics.
