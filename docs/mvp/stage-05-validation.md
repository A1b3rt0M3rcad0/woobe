# MVP Stage 05 validation

## Automated coverage

The stage is covered by the following suites:

- `tests/unit/core/test_project_overview.py`: query validation, empty-state semantics, use-case output, response envelope, and private cache headers;
- `tests/integration/core/test_project_overview_reader.py`: real PostgreSQL aggregation, project isolation, production filtering, current environment distribution, terminal-state handling, partial/unknown costs, UTC buckets under a non-UTC database session, recent traces, and the fixed seven-query budget;
- `tests/integration/core/test_project_overview_performance.py`: deterministic 30-day fixture with 3,000 terminal traces, five warmups, 100 measured executions, p95 below 500 ms, and `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` evidence that the terminal-trace partial index is eligible.

## Required commands

```bash
uv run ruff check src tests
uv run pyright \
  src/modules/core/application/composers/get_project_overview_composer.py \
  src/modules/core/infra/database/unit_of_work.py \
  src/modules/core/infra/database/uow_project_overview_reader.py \
  src/modules/core/infra/database/project_overview_reader.py
uv run alembic upgrade head
uv run alembic check
uv run pytest tests/unit/core/test_project_overview.py -q
uv run pytest tests/integration/core/test_project_overview_reader.py -q
uv run pytest tests/integration/core/test_project_overview_performance.py -q
uv run python scripts/ci/run_pytest_baseline.py
```

## Metric decisions

- Request, latency, success, failure, token, and cost metrics include only `completed`, `failed`, and `cancelled` traces.
- `cancelled` contributes to failed requests and to the success-rate denominator.
- Empty windows return zero requests and zero cost, with latency and success rate represented as unavailable.
- A non-empty window with no known costs returns `cost_usd = null`; mixed known and unknown costs return the known subtotal plus `unknown_cost_count`.
- The environment filter uses each agent's current environment, derived from its latest release. This is a current operational dashboard, not a historical deployment-at-execution report.
- Bucket boundaries are UTC even when the PostgreSQL connection session uses another timezone.

## Rollback

1. revert the stage 05 merge commit;
2. run `uv run alembic downgrade 0027` to remove only the overview indexes if the migration was deployed;
3. deploy the previous backend artifact;
4. hide the overview UI capability until the endpoint is restored;
5. do not delete trace, release, document, or tool data, because the endpoint is an aggregate read model over existing records.
