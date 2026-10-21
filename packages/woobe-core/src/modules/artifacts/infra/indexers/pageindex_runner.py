"""Resource-bounded runner for the pinned, model-free PageIndex Flash path."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import sys

from modules.artifacts.application.contracts.processing import ProcessingRecipe
from modules.artifacts.domain.models import ArtifactError, CanonicalDocument, DocumentIndex, Revision
from modules.artifacts.infra.indexers.pageindex_adapter import (
    PAGEINDEX_MAX_BYTES, PAGEINDEX_MAX_PAGES, PAGEINDEX_MAX_TIMEOUT_SECONDS,
    PAGEINDEX_VERSION, build_pageindex_tree,
)
from modules.artifacts.infra.storage.scratch import artifact_scratch
from shared.infra.object_storage.io import run_blocking


MAX_RESULT_BYTES = 67_108_864


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError('unsupported JSON constant')


class PageIndexRunner:
    name, version = 'pageindex-flash', PAGEINDEX_VERSION

    async def index(self, document: CanonicalDocument, *, index_id: str, representation_set_id: str,
                    profile: ProcessingRecipe, revision: Revision,
                    content, model=None) -> DocumentIndex:
        if model is not None:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex Flash does not use a model gateway')
        if revision.content_type.split(';', 1)[0].strip().lower() != 'application/pdf':
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex Flash accepts PDF originals only')
        if revision.size_bytes > min(profile.limits.max_bytes, PAGEINDEX_MAX_BYTES):
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PDF exceeds the selected PageIndex byte limit')
        with artifact_scratch(index_id) as scratch:
            source_path = scratch / 'source.pdf'
            digest, size = hashlib.sha256(), 0
            try:
                with source_path.open('xb') as output:
                    async for chunk in content:
                        if not isinstance(chunk, bytes) or size + len(chunk) > revision.size_bytes:
                            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'PageIndex source exceeded its declared size')
                        await run_blocking(output.write, chunk)
                        digest.update(chunk)
                        size += len(chunk)
            finally:
                close = getattr(content, 'aclose', None)
                if close is not None:
                    await close()
            if size != revision.size_bytes or digest.hexdigest() != revision.sha256:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'PageIndex source failed revision integrity verification')
            try:
                await self._run_child(scratch, min(profile.limits.timeout_seconds, PAGEINDEX_MAX_TIMEOUT_SECONDS),
                    min(profile.limits.max_pages, PAGEINDEX_MAX_PAGES))
            except ArtifactError:
                raise
            except (OSError, asyncio.SubprocessError) as error:
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex child could not be started') from error
            error_path, result_path = scratch / 'error.json', scratch / 'result.json'
            if error_path.exists():
                return self._read_error(error_path)
            if result_path.is_symlink() or not result_path.is_file() or result_path.stat().st_size > MAX_RESULT_BYTES:
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex child returned no bounded result')
            raw = await run_blocking(result_path.read_bytes)
            try:
                payload = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex child returned invalid JSON') from error
            try:
                return build_pageindex_tree(document, index_id, representation_set_id, payload)
            except ArtifactError:
                raise
            except (TypeError, ValueError, KeyError, AttributeError) as error:
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex output does not match canonical source bounds') from error

    async def _run_child(self, scratch: Path, timeout_seconds: int, max_pages: int):
        source_root = str(Path(__file__).resolve().parents[4])
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
               'PYTHONPATH': source_root, 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1',
               'MKL_NUM_THREADS': '1', 'NUMEXPR_MAX_THREADS': '1'}
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(sys.executable, '-m',
            'modules.artifacts.infra.indexers.pageindex_child', str(scratch), str(timeout_seconds),
            str(max_pages), env=env,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL, start_new_session=True))
        try:
            process = await asyncio.shield(spawn)
        except asyncio.CancelledError:
            process = await spawn
            await self._kill(process)
            raise
        try:
            async with asyncio.timeout(timeout_seconds):
                await process.wait()
        except TimeoutError as error:
            await self._kill(process)
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PageIndex exceeded its configured time limit') from error
        except asyncio.CancelledError:
            await self._kill(process)
            raise
        if process.returncode != 0 and not (scratch / 'error.json').is_file():
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex child terminated without a result')

    @staticmethod
    async def _kill(process):
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        await process.wait()

    @staticmethod
    def _read_error(path):
        if path.is_symlink() or path.stat().st_size > 4096:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex child returned invalid diagnostics')
        try:
            data = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
            code = data.get('code')
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, AttributeError) as error:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex child returned invalid diagnostics') from error
        allowed = {'ARTIFACT_LIMIT_EXCEEDED', 'PDF_INVALID_DOCUMENT', 'PDF_PASSWORD_REQUIRED',
                   'PROCESSOR_UNAVAILABLE'}
        if code not in allowed:
            code = 'PROCESSOR_UNAVAILABLE'
        raise ArtifactError(code, 'PageIndex could not build a bounded local outline')
