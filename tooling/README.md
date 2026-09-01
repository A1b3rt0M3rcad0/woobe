# Engineering tooling

`tooling/` contains development and repository-engineering packages that support Woobe without becoming part of the production runtime dependency graph.

## Contents

| Tool | Responsibility |
| --- | --- |
| `quality-gate` | Executable architecture checker, declarative policies and responsibility contracts used to prevent structural regressions. |
| `woobe-testkit` | Shared test-only helpers used across backend test suites. |
| `woobe-mock` | Protocol mocks, simulators and fault-injection utilities for external dependencies. |

These packages may be installed by development and test environments. Product packages under `packages/` must not import them at runtime. If a capability is required by the shipped application, it belongs in the appropriate product package rather than here.
