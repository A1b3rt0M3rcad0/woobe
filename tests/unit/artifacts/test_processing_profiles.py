from dataclasses import replace
import sys
from uuid import uuid4

from pydantic import ValidationError
import pytest

from modules.artifacts.application.contracts.processing import (
    ComponentReference, LibraryPin, ProcessingLimits, ProcessingModelReference,
    ProcessingParameters, ProcessingRecipe,
)
from modules.artifacts.application.processing_registry import (
    ComponentDescriptor, ProcessingRegistry, processing_fingerprint,
)
from modules.artifacts.domain.models import ArtifactError
from modules.artifacts.infra.processing.readiness import probe_distribution


def descriptor(**changes):
    return replace(ComponentDescriptor('native-test', '1', 'processor', 'original', 'canonical',
        frozenset({'text/plain'}), libraries=(LibraryPin(name='python', version='3.14.8'),),
        available=True, diagnostic=''), **changes)


def recipe(**changes):
    return ProcessingRecipe(mode='extract', processor=ComponentReference(name='native-test', version='1'), **changes)


def test_store_only_is_explicit_and_never_imports_optional_parsers_or_models():
    before = set(sys.modules)
    registry = ProcessingRegistry()
    value = registry.normalize(ProcessingRecipe())
    assert registry.readiness(value) == {'ready': True, 'diagnostics': (), 'mode': 'store_only'}
    assert registry.capabilities() == ()
    assert not {'docling', 'pageindex', 'torch', 'transformers', 'openai'} & (set(sys.modules) - before)


@pytest.mark.parametrize('invalid', [
    {'mode': 'extract'},
    {'mode': 'store_only', 'processor': {'name': 'native-test', 'version': '1'}},
    {'mode': 'extract_index', 'processor': {'name': 'native-test', 'version': '1'}},
    {'api_key': 'must never enter the recipe'},
    {'parameters': {'password': 'must never enter parameters'}},
    {'model': {'configuration_key_id': 'sk-not-a-reference', 'configuration_revision': 1,
               'model_id': str(uuid4()), 'model_revision': 1}},
    {'limits': {'max_bytes': 0}},
])
def test_invalid_and_secret_bearing_configuration_is_rejected(invalid):
    with pytest.raises(ValidationError):
        ProcessingRecipe.model_validate(invalid)


def test_library_version_model_and_parameter_changes_invalidate_processing_identity():
    registry = ProcessingRegistry((descriptor(),))
    value = registry.normalize(recipe())
    first = processing_fingerprint(sha256='a' * 64, size_bytes=7, content_type='text/plain', recipe=value)
    assert first == processing_fingerprint(sha256='a' * 64, size_bytes=7, content_type='text/plain', recipe=registry.normalize(recipe()))
    changed_library = ProcessingRegistry((descriptor(libraries=(LibraryPin(name='python', version='3.14.9'),)),)).normalize(recipe())
    changed_parameter = registry.normalize(recipe(parameters=ProcessingParameters(preserve_blank_lines=False)))
    changed_parser = ProcessingRegistry((descriptor(version='2'),)).normalize(
        ProcessingRecipe(mode='extract', processor=ComponentReference(name='native-test', version='2')))
    for changed in (changed_library, changed_parameter, changed_parser):
        assert first != processing_fingerprint(sha256='a' * 64, size_bytes=7, content_type='text/plain', recipe=changed)
    assert first != processing_fingerprint(sha256='b' * 64, size_bytes=7, content_type='text/plain', recipe=value)
    with pytest.raises(ValueError):
        registry.normalize(recipe(libraries=(LibraryPin(name='python', version='0'),)))


def test_missing_optional_dependency_and_unsupported_media_never_claim_ready():
    available, reason = probe_distribution('woobe-nonexistent-optional-processing-library', '1')
    assert not available and reason == 'dependency_not_installed'
    registry = ProcessingRegistry((descriptor(available=available, diagnostic=reason),))
    state = registry.readiness(recipe(), content_type='application/pdf')
    assert not state['ready'] and len(state['diagnostics']) == 2
    assert registry.capabilities()[0]['media_types'] == []
    with pytest.raises(ArtifactError) as failure:
        ProcessingRegistry().normalize(recipe())
    assert failure.value.code == 'PROCESSOR_UNAVAILABLE'
    with pytest.raises(ArtifactError) as failure:
        ProcessingRegistry((descriptor(max_pages=1),)).normalize(recipe())
    assert failure.value.code == 'ARTIFACT_LIMIT_EXCEEDED'


def test_ocr_indexing_and_model_enrichment_are_separate_explicit_components():
    processor = descriptor(supports_ocr=True)
    indexer = descriptor(name='tree', role='indexer', input_kind='canonical', output_kind='index')
    ocr = descriptor(name='ocr', role='ocr')
    enricher = descriptor(name='summary', role='enricher', input_kind='canonical', output_kind='enrichment')
    registry = ProcessingRegistry((processor, indexer, ocr, enricher))
    model = ProcessingModelReference(configuration_key_id=uuid4(), configuration_revision=1, model_id=uuid4(), model_revision=1)
    value = ProcessingRecipe(mode='extract_index', processor=ComponentReference(name='native-test', version='1'),
        indexer=ComponentReference(name='tree', version='1'), ocr=ComponentReference(name='ocr', version='1'),
        enricher=ComponentReference(name='summary', version='1'), model=model, limits=ProcessingLimits())
    assert not registry.readiness(value)['ready']
    assert registry.readiness(value, model_binding_ready=True)['ready']
    assert value.fingerprint() != value.model_copy(update={'model': model.model_copy(update={'model_revision': 2})}).fingerprint()
    with pytest.raises(ValueError):
        ProcessingRegistry((descriptor(), indexer, ocr, enricher)).normalize(value)
