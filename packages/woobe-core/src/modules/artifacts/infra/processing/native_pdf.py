import asyncio
from dataclasses import asdict
import hashlib
import json
import os
import signal
import sys

from modules.artifacts.application.document_codec import decode_canonical
from modules.artifacts.domain.models import ArtifactError
from modules.artifacts.infra.storage.scratch import artifact_scratch
from shared.infra.object_storage.io import run_blocking


class NativePdfProcessor:
    name, version = 'native-pdf', '1'
    media_types = frozenset({'application/pdf'})
    child_module = 'modules.artifacts.infra.processing.pdf_child'
    failure_code = 'PDF_INVALID_DOCUMENT'

    def __init__(self, *, memory_bytes=1_610_612_736, threads=2):
        if not 536_870_912 <= memory_bytes <= 8_589_934_592 or not 1 <= threads <= 8:
            raise ValueError('Invalid isolated document worker resource budget')
        self.memory_bytes, self.threads = memory_bytes, threads

    def source_name(self, revision):
        return 'source.pdf'

    async def _execute(self, revision, content, recipe, operation, **options):
        if revision.content_type.split(';', 1)[0].strip().lower() not in self.media_types:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Document processor does not support the declared media type')
        if revision.size_bytes > recipe.limits.max_bytes:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document original exceeds its byte limit')
        with artifact_scratch(self.name) as scratch:
            digest, size = hashlib.sha256(), 0
            try:
                with (scratch / self.source_name(revision)).open('wb') as output:
                    async for chunk in content:
                        if not isinstance(chunk, bytes) or size + len(chunk) > revision.size_bytes:
                            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document stream exceeds its declared size')
                        await run_blocking(output.write, chunk)
                        digest.update(chunk)
                        size += len(chunk)
            finally:
                close = getattr(content, 'aclose', None)
                if close is not None:
                    await close()
            if size != revision.size_bytes or digest.hexdigest() != revision.sha256:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document original failed integrity verification')
            command = {'operation': operation, 'revision': asdict(revision),
                       'recipe': recipe.model_dump(mode='json'), 'source_name': self.source_name(revision),
                       'memory_bytes': self.memory_bytes, 'threads': self.threads, **options}
            (scratch / 'command.json').write_text(json.dumps(command))
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(sys.executable, '-m',
                self.child_module, str(scratch),
                env={'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
                     'OMP_NUM_THREADS': str(self.threads), 'OPENBLAS_NUM_THREADS': str(self.threads),
                     'MKL_NUM_THREADS': str(self.threads), 'NUMEXPR_MAX_THREADS': str(self.threads),
                     'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'},
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL, start_new_session=True))
            process = None
            try:
                process = await asyncio.shield(spawn)
                async with asyncio.timeout(recipe.limits.timeout_seconds):
                    await process.wait()
            finally:
                if process is None:
                    process = await asyncio.shield(spawn)
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    await asyncio.shield(process.wait())
            error_path = scratch / 'error.json'
            if error_path.exists():
                if error_path.stat().st_size > 4096:
                    raise ArtifactError(self.failure_code, 'Document subprocess returned invalid diagnostics')
                error = json.loads(error_path.read_bytes())
                raise ArtifactError(error['code'], error['message'])
            output = scratch / 'output'
            maximum = min(536_870_912, recipe.limits.max_bytes * 16 + 1_048_576) if operation == 'extract' else 67_108_864
            if process.returncode != 0 or not output.is_file():
                raise ArtifactError(self.failure_code, 'Document subprocess exceeded its resource budget or failed')
            if output.stat().st_size > maximum:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document output exceeds its bounded byte limit')
            return await run_blocking(output.read_bytes)

    async def process(self, revision, content, profile):
        return decode_canonical(await self._execute(revision, content, profile, 'extract'))

    async def render(self, revision, content, profile, *, page_index, dpi=150, max_pixels=16_000_000):
        if not 1 <= max_pixels <= 16_000_000:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Invalid rendering pixel budget')
        return await self._execute(revision, content, profile, 'render', page_index=page_index,
                                   dpi=dpi, max_pixels=max_pixels)
