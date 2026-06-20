from __future__ import annotations

import pytest

from tests.performance.release_load import Sample, percentile, summarize


def test_percentile_uses_nearest_rank_for_release_thresholds() -> None:
    values = [float(value) for value in range(1, 101)]
    assert percentile(values, 0.50) == 50.0
    assert percentile(values, 0.95) == 95.0
    assert percentile(values, 0.99) == 99.0


@pytest.mark.parametrize("quantile", [-0.01, 1.01])
def test_percentile_rejects_invalid_quantiles(quantile: float) -> None:
    with pytest.raises(ValueError, match="quantile"):
        percentile([1.0], quantile)


def test_summary_reports_latency_ttft_errors_and_throughput() -> None:
    report = summarize(
        [
            Sample(latency_ms=10.0, ttft_ms=3.0, status_code=200),
            Sample(latency_ms=20.0, ttft_ms=4.0, status_code=200),
            Sample(latency_ms=30.0, ttft_ms=None, status_code=503, error="provider unavailable"),
            Sample(latency_ms=40.0, ttft_ms=6.0, status_code=200),
        ],
        concurrency=2,
        duration_seconds=2.0,
    )

    assert report.requests == 4
    assert report.errors == 1
    assert report.error_rate == 0.25
    assert report.latency_p50_ms == 20.0
    assert report.latency_p95_ms == 40.0
    assert report.latency_p99_ms == 40.0
    assert report.ttft_p50_ms == 4.0
    assert report.ttft_p95_ms == 6.0
    assert report.throughput_rps == 2.0
