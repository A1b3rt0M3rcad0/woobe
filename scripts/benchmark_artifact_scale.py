"""Reproducible PostgreSQL cardinality/performance harness for Artifact catalogs.

Requires WOOBE_ARTIFACT_BENCH_POSTGRES_URL to point at an isolated PostgreSQL
server whose login can create/drop a disposable database and run project
migrations. No application database URL is used as a fallback.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import UTC, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
SHA = hashlib.sha256(b"synthetic benchmark evidence").hexdigest()
TEXT = "needle synthetic benchmark source"
TEXT_SHA = hashlib.sha256(TEXT.encode()).hexdigest()


def _copy_rows(cursor, table: str, columns: tuple[str, ...], rows, *, batch_size=10_000):
    statement = sql.SQL("COPY artifacts.{} ({}) FROM STDIN WITH (FORMAT CSV)").format(
        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, columns)),
    )
    batch = []
    total = 0
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            buffer = io.StringIO()
            writer = csv.writer(buffer, lineterminator="\n")
            writer.writerows(batch)
            buffer.seek(0)
            cursor.copy_expert(statement.as_string(cursor), buffer)
            total += len(batch)
            batch.clear()
    if batch:
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator="\n").writerows(batch)
        buffer.seek(0)
        cursor.copy_expert(statement.as_string(cursor), buffer)
        total += len(batch)
    return total


def _seed(base_url, args):
    database = "woobe_artifact_bench_" + uuid4().hex
    admin = psycopg2.connect(base_url.set(database="postgres").render_as_string(hide_password=False))
    admin.autocommit = True
    with admin.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    database_url = base_url.set(database=database)
    migration_env = os.environ | {
        "WOOBE_POSTGRES_URL": database_url.render_as_string(hide_password=False),
    }
    migrate = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "packages/woobe-core/alembic.ini", "upgrade", "head"],
        cwd=ROOT, env=migration_env, capture_output=True, text=True,
    )
    if migrate.returncode:
        admin.cursor().execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
        admin.close()
        raise RuntimeError("Artifact benchmark migration failed: " + migrate.stderr[-4000:])

    project_id = str(uuid4())
    connection = psycopg2.connect(database_url.render_as_string(hide_password=False))
    connection.autocommit = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO core.projects (id,workspace_id,name,slug,status,data) "
                "VALUES (%s,%s,'Synthetic Artifact scale benchmark','artifact-scale-bench','active','{}')",
                (project_id, str(uuid4())),
            )
            workspaces = _copy_rows(cursor, "workspaces", (
                "id", "project_id", "environment", "external_namespace", "external_key", "name",
                "storage_profile", "status", "version", "catalog_version", "search_version", "quota_bytes",
                "used_bytes", "reserved_bytes", "retention_days", "labels", "processing_sequence",
            ), (
                (f"bench-ws-{ws:05d}", project_id, "draft", "synthetic-bench", f"workspace-{ws:05d}",
                 f"Synthetic workspace {ws:05d}", "local", "active", 1, 1, 0, 1_000_000_000,
                 0, 0, 30, "{}", 0)
                for ws in range(args.workspaces)
            ))
            artifacts = args.workspaces * args.artifacts_per_workspace
            _copy_rows(cursor, "artifacts", (
                "id", "workspace_id", "path", "kind", "revision_id", "version", "deleted",
            ), (
                (f"bench-a-{i:09d}", f"bench-ws-{i // args.artifacts_per_workspace:05d}",
                 f"needle-report-{i:09d}.txt", "file", None, 1, False)
                for i in range(artifacts)
            ))
            _copy_rows(cursor, "revisions", (
                "id", "workspace_id", "artifact_id", "object_key", "content_type", "size_bytes",
                "sha256", "origin", "producer_id", "operation_id", "source_refs",
            ), (
                (f"bench-r-{i:09d}", f"bench-ws-{i // args.artifacts_per_workspace:05d}",
                 f"bench-a-{i:09d}",
                 f"projects/{project_id}/environments/draft/artifact-workspaces/"
                 f"bench-ws-{i // args.artifacts_per_workspace:05d}/artifacts/bench-a-{i:09d}/"
                 f"revisions/bench-r-{i:09d}/original",
                 "text/plain", len(b"synthetic"), SHA, "upload", "bench", f"bench-op-{i:09d}", "[]")
                for i in range(artifacts)
            ))
            cursor.execute(
                "UPDATE artifacts.artifacts SET revision_id = 'bench-r-' || "
                "substring(id from '([0-9]{9})$')"
            )
            _copy_rows(cursor, "head_history", (
                "id", "workspace_id", "artifact_id", "from_catalog_version", "until_catalog_version",
                "path", "kind", "revision_id", "artifact_version", "deleted",
            ), (
                (f"bench-h-{i:09d}", f"bench-ws-{i // args.artifacts_per_workspace:05d}",
                 f"bench-a-{i:09d}", 1, None, f"needle-report-{i:09d}.txt", "file",
                 f"bench-r-{i:09d}", 1, False)
                for i in range(artifacts)
            ))

            represented_workspaces = min(args.workspaces, args.block_representations)
            job_rows = []
            generation_rows = []
            for ws in range(represented_workspaces):
                artifact_number = ws * args.artifacts_per_workspace
                workspace_id = f"bench-ws-{ws:05d}"
                artifact_id = f"bench-a-{artifact_number:09d}"
                revision_id = f"bench-r-{artifact_number:09d}"
                job_id = f"bench-job-{ws:05d}"
                generation_id = f"bench-set-{ws:05d}"
                job_rows.append((
                    job_id, project_id, "draft", workspace_id, artifact_id, revision_id,
                    "benchmark-runtime", "{}", f"bench-op-job-{ws:05d}", SHA, SHA, None, None,
                    "{}", SHA, 0, "succeeded", 1, 1, 1, "benchmark", "{}", None, None, False,
                ))
                generation_rows.append((
                    generation_id, project_id, "draft", workspace_id, artifact_id, revision_id,
                    job_id, 0, 1, 0, None, SHA, SHA, SHA, None, None, "building", "complete",
                    False, 0, 0, 0, 0, "[]", "[]",
                ))
            # These two tables are shared-domain ORM models mapped to the
            # artifacts schema; they exist only to distribute block rows.
            cursor.copy_expert(
                "COPY artifacts.processing_jobs (id,project_id,environment,workspace_id,artifact_id,"
                "revision_id,principal_id,principal_snapshot,operation_id,request_fingerprint,"
                "processing_fingerprint,profile_id,profile_revision,recipe,recipe_fingerprint,"
                "generation_number,status,attempt,max_attempts,fencing_token,worker_id,checkpoints,"
                "result,error_code,retryable) FROM STDIN WITH (FORMAT CSV)",
                _csv_stream(job_rows),
            )
            cursor.copy_expert(
                "COPY artifacts.representation_sets (id,project_id,environment,workspace_id,artifact_id,"
                "revision_id,job_id,generation_number,build_fencing_token,publication_fencing_token,"
                "published_search_version,source_sha256,recipe_fingerprint,processing_fingerprint,"
                "profile_id,profile_revision,status,coverage,sealed,entry_count,block_count,segment_count,"
                "page_count,diagnostics,pages) FROM STDIN WITH (FORMAT CSV)",
                _csv_stream(generation_rows),
            )

            def block_rows():
                total_blocks = args.blocks
                for block in range(total_blocks):
                    ws = block % represented_workspaces
                    generation_id = f"bench-set-{ws:05d}"
                    block_id = f"bench-block-{block:09d}"
                    text_match = ws < min(100, represented_workspaces) and block == ws
                    size = len(TEXT.encode()) if text_match else 0
                    yield (
                        block_id, f"bench-ws-{ws:05d}", generation_id, block_id, block,
                        "paragraph", None,
                        json.dumps({"page_index": block % 100}, separators=(",", ":")),
                        "native", False, "[]", None, 0, size, len(TEXT) if text_match else 0,
                        TEXT_SHA if text_match else hashlib.sha256(b"").hexdigest(),
                    )

            block_count = _copy_rows(cursor, "source_blocks", (
                "id", "workspace_id", "representation_set_id", "block_id", "ordinal", "kind",
                "parent_block_id", "source_locator", "extraction_method", "inferred", "asset_ids",
                "object_id", "byte_start", "byte_end", "char_length", "sha256",
            ), block_rows(), batch_size=20_000)
            segment_count = min(100, represented_workspaces, args.blocks)
            _copy_rows(cursor, "source_segments", (
                "id", "workspace_id", "representation_set_id", "block_id", "char_start", "char_end",
                "byte_start", "byte_end", "sha256", "search_text", "search_normalized",
            ), (
                (f"bench-segment-{ws:05d}", f"bench-ws-{ws:05d}", f"bench-set-{ws:05d}",
                 f"bench-block-{ws:09d}", 0, len(TEXT), 0, len(TEXT.encode()), TEXT_SHA, TEXT,
                 TEXT.casefold())
                for ws in range(segment_count)
            ))

            runtime_key = str(uuid4())
            cursor.execute(
                "INSERT INTO artifacts.grants (id,project_id,environment,principal_id,workspace_id,"
                "external_namespace,actions,revision,revoked) VALUES (%s,%s,'draft',%s,%s,NULL,%s,1,false)",
                (str(uuid4()), project_id, f"runtime-{runtime_key}", "bench-ws-00000", '["read","search"]'),
            )
        connection.commit()
    except BaseException:
        connection.rollback()
        connection.close()
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
        admin.close()
        raise
    connection.close()
    admin.close()
    return database, database_url, project_id, runtime_key, workspaces, artifacts, block_count, segment_count


def _csv_stream(rows):
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    buffer.seek(0)
    return buffer


async def _measure(database_url, project_id, runtime_key, args):
    os.environ["WOOBE_POSTGRES_URL"] = database_url.render_as_string(hide_password=False)
    os.environ["WOOBE_DATABASE_URL"] = database_url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    sys.path[:0] = [
        str(ROOT / "packages/woobe-core/src"),
        str(ROOT / "packages/woobe-api/src"),
    ]
    from modules.artifacts.application.contracts.files import ReadFile
    from modules.artifacts.application.contracts.search import SearchDocuments
    from modules.artifacts.domain.models import Environment, Scope
    from modules.artifacts.infra.database.catalog import CatalogRepository
    from modules.artifacts.infra.database.files import FileRepository
    from modules.artifacts.infra.database.search import ArtifactSearchRepository
    from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
    from shared.security.principal import ProjectApiPrincipal

    engine = create_async_engine(os.environ["WOOBE_DATABASE_URL"], pool_size=20, max_overflow=10)
    scope = Scope(project_id, Environment.DRAFT)
    principal = ProjectApiPrincipal(
        api_key_id=runtime_key, project_id=project_id, key_prefix="bench",
        kind="runtime", authenticated_at=datetime.now(UTC),
    )

    async def measure(name, operation, iterations=100):
        samples = []
        for _ in range(iterations):
            started = time.perf_counter()
            await operation()
            samples.append((time.perf_counter() - started) * 1000)
        ordered = sorted(samples)
        return {
            "operation": name, "iterations": iterations,
            "p50_ms": round(statistics.median(ordered), 3),
            "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * .95))], 3),
            "p99_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * .99))], 3),
            "max_ms": round(max(ordered), 3),
        }

    async def resolve():
        async with ArtifactsUnitOfWork(engine) as uow:
            return await CatalogRepository(uow).workspace(scope, "bench-ws-00000")

    async def list_page(ws="bench-ws-00000"):
        async with ArtifactsUnitOfWork(engine) as uow:
            return await FileRepository(uow).page(scope, ws, directory="", catalog_version=1,
                after=None, limit=50)

    async def read_exact():
        async with ArtifactsUnitOfWork(engine) as uow:
            return await FileRepository(uow).read(ReadFile(
                principal, scope, "bench-ws-00000", "bench-a-000000000",
            ))

    async def search():
        async with ArtifactsUnitOfWork(engine) as uow:
            return await ArtifactSearchRepository(uow).search(SearchDocuments(
                principal, scope, "bench-ws-00000", query="needle", mode="text",
                limit=20, catalog_version=1, search_version=0,
            ))

    results = [
        await measure("workspace_resolve", resolve),
        await measure("artifact_list_page", list_page),
        await measure("exact_revision_metadata_read", read_exact),
        await measure("text_search", search),
    ]
    concurrent = []
    started = time.perf_counter()
    await asyncio.gather(*(list_page(f"bench-ws-{index:05d}") for index in range(min(50, args.workspaces))))
    concurrent.append((time.perf_counter() - started) * 1000)
    results.append({"operation": "50_workspace_concurrent_list", "iterations": 1,
                    "elapsed_ms": round(concurrent[0], 3)})
    async with engine.begin() as connection:
        version = (await connection.exec_driver_sql("SHOW server_version")).scalar_one()
        size = (await connection.exec_driver_sql("SELECT pg_database_size(current_database())")).scalar_one()
        plan_page = (await connection.exec_driver_sql(
            "EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) "
            "SELECT h.artifact_id FROM artifacts.head_history h "
            "JOIN artifacts.artifacts a ON a.id=h.artifact_id "
            "WHERE h.workspace_id='bench-ws-00000' AND h.from_catalog_version<=1 "
            "AND (h.until_catalog_version IS NULL OR h.until_catalog_version>1) "
            "AND NOT h.deleted AND NOT a.deleted "
            "AND h.path NOT LIKE '%/%' ORDER BY h.artifact_id LIMIT 51"
        )).scalar_one()
        plan_search = (await connection.exec_driver_sql(
            "EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) "
            "SELECT h.artifact_id FROM artifacts.head_history h "
            "WHERE h.workspace_id='bench-ws-00000' AND h.from_catalog_version<=1 "
            "AND (h.until_catalog_version IS NULL OR h.until_catalog_version>1) "
            "AND NOT h.deleted AND to_tsvector('simple'::regconfig, "
            "normalize(regexp_replace(h.path, '[^[:alnum:]]+', ' ', 'g'), NFKC)) "
            "@@ websearch_to_tsquery('simple','needle') LIMIT 20"
        )).scalar_one()
        plans = {"artifact_list": plan_page, "path_search": plan_search}
    await engine.dispose()
    return results, version, size, plans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspaces", type=int, default=10_000)
    parser.add_argument("--artifacts-per-workspace", type=int, default=10)
    parser.add_argument("--blocks", type=int, default=1_000_000)
    parser.add_argument("--block-representations", type=int, default=100)
    parser.add_argument("--report", type=Path, default=Path("/tmp/artifact-scale-report.json"))
    args = parser.parse_args()
    if min(args.workspaces, args.artifacts_per_workspace, args.blocks, args.block_representations) < 1:
        parser.error("all dataset cardinalities must be positive")
    connection_url = os.environ.get("WOOBE_ARTIFACT_BENCH_POSTGRES_URL")
    if not connection_url:
        parser.error("WOOBE_ARTIFACT_BENCH_POSTGRES_URL must point at an isolated PostgreSQL server")
    base_url = make_url(connection_url).set(drivername="postgresql")
    started = time.perf_counter()
    database, database_url, project_id, runtime_key, workspaces, artifacts, blocks, segments = _seed(base_url, args)
    seeded_seconds = time.perf_counter() - started
    admin = psycopg2.connect(base_url.set(database="postgres").render_as_string(hide_password=False))
    admin.autocommit = True
    try:
        results, pg_version, database_bytes, query_plans = asyncio.run(
            _measure(database_url, project_id, runtime_key, args),
        )
        report = {
            "schema_version": 1,
            "dataset": {
                "workspaces": workspaces, "artifacts": artifacts, "source_blocks": blocks,
                "source_segments": segments, "private_content": False,
                "workspaces_with_representations": min(args.workspaces, args.block_representations),
                "seed_seconds": round(seeded_seconds, 3),
            },
            "environment": {
                "postgres_version": pg_version, "database_bytes": database_bytes,
                "python": sys.version.split()[0], "platform": platform.platform(),
                "cpu_count": os.cpu_count(),
                "cgroup_memory_limit_bytes": _cgroup_number("/sys/fs/cgroup/memory.max"),
                "cgroup_cpu_quota": _cgroup_cpu_limit(),
            },
            "measurements": results,
            "query_plans": query_plans,
            "budgets": {"list_p95_ms": 500, "search_p95_ms": 1500},
            "limitations": [
                "Synthetic PostgreSQL metadata benchmark; no LLM, OCR or object payload throughput is measured.",
                "Database host/container resources are reported only where visible to this process.",
                "Passing this run does not qualify production scale or millions of Workspaces.",
            ],
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
        admin.close()


def _cgroup_number(path):
    try:
        value = Path(path).read_text().strip()
        return int(value) if value != "max" else None
    except (OSError, ValueError):
        return None


def _cgroup_cpu_limit():
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        return round(int(quota) / int(period), 3) if quota != "max" else None
    except (OSError, ValueError, ZeroDivisionError):
        return None


if __name__ == "__main__":
    main()
