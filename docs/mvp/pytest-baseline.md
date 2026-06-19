# Pytest baseline

The canonical module tests live under `tests/modules/**` after the service-to-application architecture migration.

The CI suite uses importlib collection mode because the repository intentionally contains repeated test basenames in separate packages.

The following legacy duplicate files remain in the repository for historical traceability but are not collected by the MVP gate because equivalent canonical suites exist under `tests/modules/**`:

- `tests/unit/test_billing/test_dtos.py`
- `tests/unit/test_billing/test_use_cases.py`
- `tests/unit/test_metering/test_dtos.py`
- `tests/unit/test_metering/test_use_cases.py`
- `tests/unit/test_observability/test_dtos.py`
- `tests/unit/test_observability/test_use_cases.py`

`tests/integration/observability/test_spec014_observability_projection.py` targets the removed pre-truthful-projector internals and is also excluded. Current observability contracts are covered by the active projector, diagnostics, timeline, and trace tests.

## Reviewed failure allowlist

The closeout audit executed the backend gate against commit `6effb6293ebe2c63b1e8f14c91f5e34fc6df7444`. The raw JUnit artifact contained 152 failing tests, 3,342 passing tests and 8 skipped tests. The previous allowlist still contained 178 hashes, so 26 already-resolved entries were silently accepted.

`tests/ci/known_pytest_failure_hashes.txt` now contains exactly the 152 failures observed in that artifact. The gate is exact and shrink-only:

- a new failure fails CI;
- a resolved failure also fails CI until its stale hash is removed in the same pull request;
- duplicate or empty baselines fail as configuration errors.

The audit-head validation at `4fb18cb2c7c5c27e625bf4370b1dccf479a932f6` produced 3,345 passing tests, 152 reviewed failures and 8 skipped tests, with `unexpected=0` and `stale=0`.

A successful baseline gate therefore means "no change in reviewed debt", not "the complete backend suite is green". Release hardening must remove the remaining allowlist and run plain `pytest -q` successfully before the MVP can be represented as fully tested.
