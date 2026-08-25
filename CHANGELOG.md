# Changelog

Woobe follows Semantic Versioning for public releases. This file records user-visible changes after the public release baseline is established.

## Unreleased

### Changed

- Product identity standardized on Woobe.
- `development` established as the integration branch for the public project.
- Community and Cloud deployment behavior separated.
- Community self-host distribution added.
- ChatSurface added to the production topology.
- Community instance bootstrap and invite-only registration policy added.

### Security

- Self-host configuration generation uses independent random secrets for authentication, persisted-secret encryption and ChatSurface session-token signing.
