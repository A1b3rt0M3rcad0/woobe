"""Private subprocess entry point for PDF layout analysis."""

import json
import os
from pathlib import Path
import resource
import sys

from modules.artifacts.domain.models import ArtifactError
from modules.artifacts.infra.indexers.pageindex_adapter import pageindex_outline


MAX_RESULT_BYTES = 67_108_864
MEMORY_BYTES = 1_610_612_736


def _limits(timeout_seconds):
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    cpu_seconds = min(3605, timeout_seconds + 5)
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_RESULT_BYTES, MAX_RESULT_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def _write_error(path, code):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps({'code': code}, separators=(',', ':')), encoding='utf-8')
    os.replace(temp, path)


def main(directory, timeout_seconds, max_pages):
    scratch = Path(directory).resolve(strict=True)
    source = scratch / 'source.pdf'
    output = scratch / 'result.json'
    error = scratch / 'error.json'
    _limits(timeout_seconds)
    try:
        result = pageindex_outline(source, max_pages=max_pages)
        raw = json.dumps(result, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        if len(raw) > MAX_RESULT_BYTES:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PageIndex result exceeds its output budget')
        output.write_bytes(raw)
    except ArtifactError as failure:
        _write_error(error, failure.code.value)
        return 1
    except BaseException:
        _write_error(error, 'PROCESSOR_UNAVAILABLE')
        return 1
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit(1)
    try:
        timeout, pages = int(sys.argv[2]), int(sys.argv[3])
        if not 1 <= timeout <= 3600 or not 1 <= pages <= 10_000:
            raise SystemExit(1)
    except ValueError:
        raise SystemExit(1)
    raise SystemExit(main(sys.argv[1], timeout, pages))
