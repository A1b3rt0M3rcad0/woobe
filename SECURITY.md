# Security Policy

## Supported versions

Woobe `v0.1.x` is the current supported public release line. Security fixes target supported releases and the `master` integration branch.

## Reporting a vulnerability

Do not open a public issue containing an exploit, credential, private deployment information or unpatched vulnerability details.

Prefer GitHub private vulnerability reporting/security advisories when available. If that channel is not enabled, contact the repository owner privately and include the affected version, impact, reproduction steps and any suggested mitigation.

Do not include production secrets, customer data or full provider credentials in a report. Redact tokens and identify them by prefix only when necessary.

## Security boundaries

Important Woobe trust boundaries include:

- control-plane user sessions and CSRF protection;
- Project and Workspace ownership/authorization;
- Runtime Keys and API-key scopes;
- provider credentials and persisted secret encryption;
- ChatSurface Access Keys versus browser Session Access Tokens;
- Tool HTTP/MCP execution;
- Knowledge uploads and object storage;
- worker/broker and database credentials.

A UUID or resource identifier is never treated as authorization by itself.

## Deployment responsibility

Self-host operators are responsible for TLS termination, secret storage, network exposure, host hardening, backups, provider credentials and timely upgrades. Production configuration validation in Woobe is a guardrail, not a substitute for infrastructure security.
