# Woobe Architecture

Woobe is an API-first control plane and runtime for versioned AI products.

## Domain boundaries

Workspace is the commercial/membership unit. Project is the technical isolation unit. Agents, Agent Network, Tools, Knowledge, Runtime Keys, Runs and Traces are Project-scoped.

Agents are configurable definitions. Agent Releases are immutable snapshots. A Project has one operational Agent Network; Network Releases are immutable snapshots of its composition. Draft is mutable, Staging is validation, and Production consumes immutable releases.

Knowledge is organized around Collections and Documents. Vector Snapshots identify the exact generated knowledge set and indexing parameters used by runtime bindings.

## Execution model

An Agent Run is one logical execution of an Agent. A Network Run coordinates one or more causally related Agent Runs. Sessions preserve longitudinal conversational context; Runs represent finite execution occurrences; Traces are observable evidence of those Runs.

HTTP, streaming and async jobs are transport/delivery forms, not separate execution ontologies.

## Runtime boundaries

Critical authorization, ownership, release immutability, duplicate-document rules, key scopes and runtime policy are enforced by the backend. The frontend reflects those rules but is not the security boundary.

Runtime infrastructure is process-separated into API and Workers. RabbitMQ supports asynchronous module/runtime work. PostgreSQL is the durable source of application state. Redis is optional where cache-backed capabilities are enabled. Knowledge files can use local persistent storage or S3-compatible storage.

## Distribution boundaries

The public repository and supported self-host distribution contain Woobe Community/Core only.

```text
Community = Core
Cloud     = proprietary Woobe-managed product built on Core, not distributed here
Enterprise = not currently implemented or distributed
```

Shared operational code belongs under `src/modules/**` and `src/shared/**`. The Community frontend lives in the normal shared frontend tree. Proprietary Cloud implementation and future proprietary edition implementation are not part of the public Community source tree.

Community composition roots such as `src/main.py`, `src/worker_main.py`, `migrations/env.py`, the root `compose.yaml`, and `web/src/app/**` must remain runnable without proprietary edition source.

Architecture tests under `tests/architecture/` protect the Community boundary and must fail if proprietary edition implementation is added to the public Community distribution unintentionally.

No empty Enterprise implementation tree is maintained. Enterprise directories should be introduced only when real Enterprise capabilities exist and their distribution model has been explicitly decided.

The Community licensing and product boundary is described by `LICENSE.md` and `LICENSING.md`. Proprietary product terms are intentionally outside this repository.
