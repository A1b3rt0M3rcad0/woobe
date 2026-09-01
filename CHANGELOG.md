# Changelog

Woobe follows Semantic Versioning for public releases. This file records user-visible changes after the public release baseline is established.

## Unreleased

### Changed

- Product identity standardized on Woobe.
- `master` established as the integration branch.
- Repository reorganized into product `packages/`, engineering `tooling/` and cross-system `tests/` boundaries.
- Product licensing model standardized on Woobe Core plus separately licensed Enterprise.
- Core self-host distribution and release images aligned with explicit Core edition metadata.
- ChatSurface separated into its own product package and container artifact.
- Core instance bootstrap and registration policy documented for self-hosting.

### Security

- Self-host configuration generation uses independent random secrets for authentication, persisted-secret encryption and ChatSurface session-token signing.
- Container artifacts run as non-root users and expose explicit Core license metadata.
