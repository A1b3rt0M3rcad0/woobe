# Runtime security constraints

Production deployments must enable the secure attribute on refresh-session cookies at the environment configuration layer.

The current login, project-key request and project-key concurrency limiters keep counters in process memory. Until a shared limiter backend is implemented, the API deployment is constrained to one replica and one application worker. The repository Dockerfile starts one Uvicorn process and does not pass a multi-worker option.

A deployment that changes the replica or worker count must first replace those limiters with a shared backend and add distributed concurrency tests.
