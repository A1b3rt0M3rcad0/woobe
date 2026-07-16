from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class Sample:
    latency_ms: float
    ttft_ms: float | None
    status_code: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LoadReport:
    requests: int
    concurrency: int
    errors: int
    error_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    ttft_p50_ms: float | None
    ttft_p95_ms: float | None
    ttft_p99_ms: float | None
    throughput_rps: float
    duration_seconds: float


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between zero and one")
    ordered = sorted(values)
    rank = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[rank]


def summarize(samples: list[Sample], *, concurrency: int, duration_seconds: float) -> LoadReport:
    latencies = [sample.latency_ms for sample in samples]
    ttfts = [sample.ttft_ms for sample in samples if sample.ttft_ms is not None]
    errors = sum(1 for sample in samples if sample.error is not None or sample.status_code >= 400)
    requests = len(samples)
    return LoadReport(
        requests=requests,
        concurrency=concurrency,
        errors=errors,
        error_rate=errors / requests if requests else 1.0,
        latency_p50_ms=percentile(latencies, 0.50),
        latency_p95_ms=percentile(latencies, 0.95),
        latency_p99_ms=percentile(latencies, 0.99),
        ttft_p50_ms=percentile(ttfts, 0.50) if ttfts else None,
        ttft_p95_ms=percentile(ttfts, 0.95) if ttfts else None,
        ttft_p99_ms=percentile(ttfts, 0.99) if ttfts else None,
        throughput_rps=requests / duration_seconds if duration_seconds > 0 else 0.0,
        duration_seconds=duration_seconds,
    )


async def _consume_stream(response: httpx.Response, started: float) -> float | None:
    first_data_at: float | None = None
    async for line in response.aiter_lines():
        if line.startswith("data: ") and first_data_at is None:
            first_data_at = time.perf_counter()
        if line == "data: [DONE]":
            break
    return (first_data_at - started) * 1_000 if first_data_at is not None else None


async def execute_one(
    client: httpx.AsyncClient,
    *,
    url: str,
    stream: bool,
    scenario: str,
) -> Sample:
    payload: dict[str, Any] = {
        "model": f"fake-{scenario}",
        "messages": [{"role": "user", "content": "release readiness"}],
        "stream": stream,
    }
    started = time.perf_counter()
    try:
        if stream:
            async with client.stream("POST", url, json=payload) as response:
                ttft_ms = await _consume_stream(response, started)
                status_code = response.status_code
        else:
            response = await client.post(url, json=payload)
            status_code = response.status_code
            ttft_ms = None
        return Sample(
            latency_ms=(time.perf_counter() - started) * 1_000,
            ttft_ms=ttft_ms,
            status_code=status_code,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 - errors are part of the load report
        return Sample(
            latency_ms=(time.perf_counter() - started) * 1_000,
            ttft_ms=None,
            status_code=0,
            error=f"{type(exc).__name__}: {exc}",
        )


async def run_load(
    *,
    url: str,
    requests: int,
    concurrency: int,
    stream: bool,
    scenario: str,
    timeout_seconds: float,
) -> LoadReport:
    if requests < 1:
        raise ValueError("requests must be positive")
    if concurrency < 1:
        raise ValueError("concurrency must be positive")

    semaphore = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)

    async with httpx.AsyncClient(timeout=timeout_seconds, limits=limits) as client:
        async def guarded() -> Sample:
            async with semaphore:
                return await execute_one(client, url=url, stream=stream, scenario=scenario)

        started = time.perf_counter()
        samples = await asyncio.gather(*(guarded() for _ in range(requests)))
        duration_seconds = time.perf_counter() - started

    return summarize(samples, concurrency=concurrency, duration_seconds=duration_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ProjectRAI deterministic release load gate")
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--scenario", default="success")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--max-p95-ms", type=float, default=500.0)
    parser.add_argument("--max-ttft-p95-ms", type=float, default=250.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=Path("release-load-report.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(
        run_load(
            url=args.url,
            requests=args.requests,
            concurrency=args.concurrency,
            stream=args.stream,
            scenario=args.scenario,
            timeout_seconds=args.timeout_seconds,
        )
    )
    args.output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
    print(args.output.read_text(), end="")

    violations = []
    if report.error_rate > args.max_error_rate:
        violations.append(f"error_rate={report.error_rate:.4f} > {args.max_error_rate:.4f}")
    if report.latency_p95_ms > args.max_p95_ms:
        violations.append(f"latency_p95_ms={report.latency_p95_ms:.2f} > {args.max_p95_ms:.2f}")
    if args.stream and report.ttft_p95_ms is not None and report.ttft_p95_ms > args.max_ttft_p95_ms:
        violations.append(f"ttft_p95_ms={report.ttft_p95_ms:.2f} > {args.max_ttft_p95_ms:.2f}")

    if violations:
        print("Release load gate failed: " + "; ".join(violations))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
