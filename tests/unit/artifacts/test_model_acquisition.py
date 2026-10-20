from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path

import pytest

from scripts.processing.acquire_models import acquire, model_files


def manifest(content=b'unit acquisition integrity fixture'):
    revision = 'a' * 40
    return {'schema_version': '1', 'models': [{'model_id': 'unit-fixture-not-a-real-model',
        'revision': revision, 'license': 'MIT', 'files': [{'path': 'weights/data.bin',
            'size_bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
            'url': f'https://huggingface.co/example/unit-fixture/resolve/{revision}/data.bin'}]}]}


class UnitOpener:
    def __init__(self, content):
        self.content, self.calls = content, 0

    def open(self, request, timeout):
        self.calls += 1
        return io.BytesIO(self.content)


def test_explicit_acquisition_is_immutable_verified_and_offline_replay_uses_no_network(tmp_path):
    content = b'unit acquisition integrity fixture'
    opener = UnitOpener(content)
    value = manifest(content)
    assert acquire(value, tmp_path, download=True, opener=opener) == 1
    assert (tmp_path / 'weights/data.bin').read_bytes() == content
    assert acquire(value, tmp_path, opener=opener) == 1 and opener.calls == 1
    (tmp_path / 'weights/data.bin').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='integrity'):
        acquire(value, tmp_path, download=True, opener=opener)
    assert opener.calls == 1


@pytest.mark.parametrize('actual', [b'wrong', b'unit acquisition integrity fixture extra bytes'])
def test_failed_integrity_never_publishes_an_artifact_or_leaves_private_staging(tmp_path, actual):
    with pytest.raises(ValueError):
        acquire(manifest(), tmp_path, download=True, opener=UnitOpener(actual))
    assert not (tmp_path / 'weights/data.bin').exists()
    assert not list(tmp_path.rglob('.model-*'))


@pytest.mark.parametrize('field,value', [('path', '../escape'), ('url', 'http://huggingface.co/no-tls'),
                                       ('url', 'https://unapproved.example/weights'), ('sha256', 'not-a-digest')])
def test_acquisition_rejects_unpinned_unsafe_sources(field, value):
    data = deepcopy(manifest())
    data['models'][0]['files'][0][field] = value
    with pytest.raises(ValueError):
        model_files(data)


def test_shipped_model_free_docling_manifest_requires_no_weights_or_network(tmp_path):
    root = Path(__file__).resolve().parents[3]
    value = json.loads((root / 'packages/woobe-core/src/modules/artifacts/infra/processing/manifests/docling-native-v1.json').read_bytes())
    opener = UnitOpener(b'never requested')
    assert acquire(value, tmp_path, opener=opener) == 0 and opener.calls == 0
