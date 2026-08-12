# Woobe public release checklist

This checklist separates code work from repository/legal/operational actions that cannot be completed safely by a feature branch alone.

## Required before changing repository visibility

- Review `LICENSE.md`, `TRADEMARKS.md` and `COMMERCIAL-LICENSE.md` with qualified legal counsel.
- Run `scripts/audit_public_history.sh` against a full clone and rotate/revoke every real secret found before rewriting history.
- Review historical branches/tags and decide whether the public repository keeps rewritten history or starts from a sanitized public baseline.
- Validate clean Community installation, existing-database owner bootstrap, backup/restore, production Compose, ChatSurface production topology and upgrade procedure.
- Run the manual GitHub workflows intentionally; this repository does not auto-run CI merely because a PR was opened.

## Repository administration after merge

- Set `development` as the GitHub default branch.
- Protect `development` and require PR review according to the chosen maintainer policy.
- Enable private vulnerability reporting/security advisories.
- Add repository description, topics and documentation/homepage URL.
- Enable Discussions only if the project wants community support there.
- Configure GHCR package visibility for published images.

## Explicitly deferred commercial/product work

SSO/SAML, SCIM, advanced RBAC/governance, advanced audit export, external KMS/secrets, supported HA, private networking, SLA/support automation, Kubernetes Operator, Helm, Terraform, marketplaces, social/CRM connectors and a license-entitlement server are not public-readiness blockers. They should be built only when product/customer demand justifies them.
