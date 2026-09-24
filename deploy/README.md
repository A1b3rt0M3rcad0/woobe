# Deployment support

`deploy/` contains deployment-environment support files that are intentionally separate from the canonical Core self-host contract.

## Contents

- `dev/` — optional contributor/development infrastructure and local deployment support.

The supported Core first-run topology remains root `compose.yaml`. Production and operator guidance belongs under `docs/deployment/`, `docs/SELF_HOSTING.md` and related runbooks. New deployment directories should represent a distinct supported environment rather than another copy of the default Compose stack.
