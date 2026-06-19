# Project overview performance acceptance

Target: p95 below 500 ms without network latency for the 30-day dashboard query on the representative PostgreSQL fixture.

The implementation performs seven aggregate queries regardless of the number of agents, releases, traces, documents, or tools in the project. The repository exposes `query_count = 7` so integration tests can detect accidental N+1 behavior.

Validation procedure:

1. apply migrations to an empty PostgreSQL database;
2. load the deterministic dashboard fixture covering two projects and 30 days;
3. warm the connection pool with five overview requests;
4. execute 100 requests for one project and record application-side duration;
5. require p95 below 500 ms;
6. run `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` for the summary and timeseries statements;
7. confirm that project and time predicates are present and that the terminal-trace partial index is eligible.

The endpoint response must include `Cache-Control: private, max-age=15` and `Vary: Authorization`. Performance tests must never disable project scoping or authorization to obtain a faster result.
