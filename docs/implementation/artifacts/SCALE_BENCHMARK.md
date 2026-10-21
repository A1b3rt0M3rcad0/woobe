# Artifact metadata scale rehearsal

Run on 2026-10-21 against an isolated disposable PostgreSQL 17.11 database. The
reproducible harness is `scripts/benchmark_artifact_scale.py`; the complete
measurements and query plans are in [SCALE_BENCHMARK.json](SCALE_BENCHMARK.json).

The synthetic catalog contained 10,000 Workspaces, 100,000 Artifacts and
1,000,000 distributed source-block rows (855 MB database). It used four CPU
cores and a 32 GiB visible cgroup memory limit. The fixture has no private
content or object payloads. 100 read/search samples and one concurrent 50
Workspace list were collected through the real repositories.

| Operation | p50 | p95 | p99 | Initial budget |
| --- | ---: | ---: | ---: | ---: |
| Resolve Workspace | 0.97 ms | 1.87 ms | 50.62 ms | — |
| List 50 Artifacts | 2.17 ms | 3.29 ms | 7.59 ms | 500 ms |
| Read exact revision metadata | 3.35 ms | 8.22 ms | 13.31 ms | — |
| Text search | 5.96 ms | 12.09 ms | 25.95 ms | 1,500 ms |
| 50 concurrent Workspace lists | — | 594.51 ms total | — | — |

Both budgeted p95 measurements passed in this environment. Resolve has one
50.62 ms outlier; it remains in the reported p99/max and was not discarded.
The report includes PostgreSQL `EXPLAIN ANALYZE` plans, database size, runtime,
platform and visible resource limits.

This was a synthetic **metadata** rehearsal. It did not measure byte transfer,
concurrent uploads/jobs, OCR, PageIndex processing, broker/Redis outages,
production fairness, production-scale cardinalities or an LLM. The result is
not a production SLO and does not qualify millions of Workspaces. The lifecycle
PostgreSQL tests separately inject storage-delete failure and verify retry and
scope isolation; they are not a substitute for the unavailable broker/Redis
failure rehearsal.
