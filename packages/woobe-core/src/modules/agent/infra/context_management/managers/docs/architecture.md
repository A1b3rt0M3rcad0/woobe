# Architecture and mental model

A Context Manager is the algorithm that decides how candidate context is selected and configured before one Model Invocation.

```text
Concrete Context Manager
        |
        v
ContextManagerContext
├── candidates
├── budget
├── sources
└── complete()
        |
        v
Context Manager Runtime
├── source materialization
├── provider-safe assembly
├── global budget enforcement
├── Context Snapshot
├── contribution provenance
└── integrity/hash accounting
        |
        v
ContextAssembler
        |
        v
Model Invocation
```

## What a Manager owns

A Manager may decide:

- allowed context sources;
- Session window policy;
- per-source caps;
- deduplication;
- ordering;
- budget and pressure policy;
- optional runtime sources such as Run-local Skills.

## What the Runtime owns

A Manager must not construct Context Snapshots, Context Contributions, hashes, provider messages, or provenance metadata directly.

The shared Runtime owns:

- materialization mechanics;
- mandatory system/current-input invariants;
- model-capacity clamping;
- reserved-output accounting;
- global overflow handling;
- source transformations;
- Context Snapshot generation;
- contribution provenance;
- integrity hashes.

The rule is the same as Execution Strategy:

> Concrete code owns the algorithm. Runtime code owns execution mechanics and invariants.

## Stable identity

Context Managers use unversioned semantic identities:

```text
standard
adaptive
long-horizon
```

Historical `stdcm:v1`, `stdcm:v2`, and `default:v1` snapshots are compatibility inputs only. New snapshots persist the stable Manager name.
