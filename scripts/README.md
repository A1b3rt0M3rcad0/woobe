# Repository scripts

`scripts/` contains explicit operational, development and repository-maintenance entrypoints. Scripts orchestrate existing product capabilities; they should not become a second home for business rules.

## What lives here

- environment/bootstrap utilities such as self-host environment generation and instance initialization;
- PostgreSQL backup, restore and migration entrypoints;
- CI runner coordination and Docker-access helpers under `ci/`;
- smoke, release-history and repository validation utilities;
- messaging-related operational scripts under `messaging/`;
- deterministic demo/bootstrap helpers used by documented workflows.

Scripts that are part of a supported user/operator flow must have predictable inputs, fail clearly and remain aligned with the canonical Compose and package paths. Reusable application behavior belongs in `packages/`, not in shell or one-off Python orchestration.
