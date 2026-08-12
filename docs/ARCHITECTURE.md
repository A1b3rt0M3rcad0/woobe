# Woobe Architecture

Woobe is an API-first control plane and runtime for versioned AI products.

## Domain boundaries

Organization is the commercial/membership unit. Project is the technical isolation unit. Agents, Agent Network, Tools, Knowledge, Runtime Keys, Runs and Traces are Project-scoped.

Agents are configurable definitions. Agent Releases are immutable snapshots. A Project has one operational Agent Network; Network Releases are immutable snapshots of its composition. Draft is mutable, Staging is validation, and Production consumes immutable releases.

Knowledge is organized around Collections and Documents. Vector Snapshots identify the exact generated knowledge set and indexing parameters used by runtime bindings.

## Execution model

An Agent Run is one logical execution of an Agent. A Network Run coordinates one or more causally related Agent Runs. Sessions preserve longitudinal conversational context; Runs represent finite execution occurrences; Traces are observable evidence of those Runs.

HTTP, streaming and async jobs are transport/delivery forms, not separate execution ontologies.

## Runtime boundaries

Critical authorization, ownership, release immutability, duplicate-document rules, key scopes and runtime policy are enforced by the backend. The frontend reflects those rules but is not the security boundary.

Runtime infrastructure is process-separated into API and Workers. RabbitMQ supports asynchronous module/runtime work. PostgreSQL is the durable source of application state. Redis is optional where cache-backed capabilities are enabled. Knowledge files can use local persistent storage or S3-compatible storage.

## Community, Cloud and Enterprise

Community contains the operational core and can run without Woobe Cloud. Cloud adds managed commercial/operational capabilities around the same core. Enterprise capabilities are reserved for organization-scale governance/security requirements and are not implemented merely to create artificial Community limitations.
