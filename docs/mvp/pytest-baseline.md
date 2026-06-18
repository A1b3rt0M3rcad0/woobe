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
