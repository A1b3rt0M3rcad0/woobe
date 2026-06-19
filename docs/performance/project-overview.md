# Project overview performance acceptance

Target: p95 below 500 ms without network latency for the 30-day dashboard query on the representative PostgreSQL fixture.

The implementation performs seven aggregate queries regardless of the number of agents, releases, traces, documents, or tools in the project. The integration suite instruments SQLAlchemy's `before_cursor_execute` event and fails if one overview request exceeds the seven-query budget.

Automated fixture:

1. apply all migrations to PostgreSQL;
2. create an isolated project and 3,000 terminal traces distributed across 30 days;
3. warm the connection pool with five overview requests;
4. execute and measure 100 overview requests;
5. require application-side p95 below 500 ms;
6. run `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` for the project/time/status predicate;
7. require the `ix_observability_traces_project_started_terminal` partial index to appear in the plan when sequential scans are disabled to verify index eligibility.

The functional integration fixture separately covers two projects, current production/staging/draft classification, terminal and non-terminal traces, known and unknown costs, and a PostgreSQL session configured to `America/Sao_Paulo` while asserting UTC bucket boundaries.

The endpoint response includes `Cache-Control: private, max-age=15` and `Vary: Authorization`. Performance validation never removes project scoping or authorization from the product endpoint.
