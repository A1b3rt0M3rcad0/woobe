# GitHub repository automation

`.github/` contains GitHub-specific repository metadata and automation. Changes here can alter pull-request policy, CI behavior, security validation, contribution acceptance and release mechanics even though this directory contains no product runtime code.

## Contents

- `workflows/` — GitHub Actions workflows for backend tests, Frontend validation, Package Build, Acceptance, Quality Gate, Container Quality, Security, CLA validation, automated release preparation, immutable release-candidate builds, automatic Git tagging, Core image promotion, post-publish validation and GitHub Release publication.
- `ISSUE_TEMPLATE/` — structured issue templates.
- `PULL_REQUEST_TEMPLATE.md` — canonical pull-request checklist, product/license impact and contribution metadata.

Workflows should invoke repository-owned scripts and documented validation contracts rather than embedding a second implementation of those contracts. CI changes must preserve branch, security, licensing and release invariants explicitly.
