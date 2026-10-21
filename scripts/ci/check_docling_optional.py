"""Verify the real API import and optional capability in the selected venv."""
import argparse
import asyncio
import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
for package in ('woobe-core', 'woobe-api', 'woobe-workers'):
    sys.path.insert(0, str(ROOT / 'packages' / package / 'src'))


async def check(available):
    from main import app
    from modules.artifacts.entrypoint import processing_component_capabilities
    from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe
    from modules.artifacts.domain.models import ArtifactError, Revision
    from modules.artifacts.infra.processing.docling_native import DoclingNativeProcessor

    assert '/v1/artifact-processing-capabilities' in app.openapi()['paths']
    assert not ({'docling', 'docling_core', 'torch'} & set(sys.modules)), 'API import loaded an optional converter'
    component = next(item for item in processing_component_capabilities() if item['name'] == 'docling-native')
    assert component['ready'] == available, component
    if not available:
        assert component['media_types'] == []
        content = b'%PDF-1.7\n'
        revision = Revision('revision', 'artifact', 'objects/original', 'application/pdf',
                            len(content), hashlib.sha256(content).hexdigest(), 'upload')
        async def stream():
            yield content
        try:
            await DoclingNativeProcessor().process(revision, stream(), ProcessingRecipe(mode='extract',
                processor=ComponentReference(name='docling-native', version='2.140.0')))
        except ArtifactError as error:
            assert error.code == 'PROCESSOR_UNAVAILABLE', error.code
        else:
            raise AssertionError('Missing optional converter executed successfully')
    print('API import is converter-free; optional Docling ready=' + str(available))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--available', action='store_true')
    asyncio.run(check(parser.parse_args().available))
