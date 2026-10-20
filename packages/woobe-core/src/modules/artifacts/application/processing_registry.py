from dataclasses import dataclass
import hashlib
import json
from typing import Literal

from modules.artifacts.application.contracts.processing import ComponentReference, LibraryPin, ProcessingRecipe
from modules.artifacts.domain.models import ArtifactError, sha256_digest


@dataclass(frozen=True)
class ComponentDescriptor:
    name: str
    version: str
    role: Literal['processor', 'indexer', 'ocr', 'enricher']
    input_kind: Literal['original', 'canonical', 'index']
    output_kind: Literal['canonical', 'index', 'enrichment']
    media_types: frozenset[str]
    libraries: tuple[LibraryPin, ...] = ()
    max_bytes: int = 536_870_912
    max_pages: int = 10_000
    timeout_seconds: int = 3600
    available: bool = False
    diagnostic: str = 'implementation_unavailable'
    supports_ocr: bool = False

    def __post_init__(self):
        ComponentReference(name=self.name, version=self.version)
        if self.role not in {'processor', 'indexer', 'ocr', 'enricher'}:
            raise ValueError('Unknown processing component role')
        expected = {'processor': 'canonical', 'ocr': 'canonical', 'indexer': 'index', 'enricher': 'enrichment'}
        if self.output_kind != expected[self.role]:
            raise ValueError('Processing component has an incompatible output contract')
        if min(self.max_bytes, self.max_pages, self.timeout_seconds) < 1:
            raise ValueError('Component limits must be positive')


class ProcessingRegistry:
    """Passive declarations and injected readiness; never imports a converter."""

    def __init__(self, components: tuple[ComponentDescriptor, ...] = ()):
        self._components = {(item.role, item.name, item.version): item for item in components}
        if len(self._components) != len(components):
            raise ValueError('Processing component declarations must be unique')

    def normalize(self, recipe: ProcessingRecipe):
        libraries = {}
        for role in ('processor', 'indexer', 'ocr', 'enricher'):
            selected = getattr(recipe, role)
            if selected is None:
                continue
            descriptor = self._components.get((role, selected.name, selected.version))
            if descriptor is None:
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Processing component/version is not registered')
            if ((role in {'processor', 'ocr'} and descriptor.input_kind != 'original')
                or (role in {'indexer', 'enricher'} and descriptor.input_kind not in {'canonical', 'index'})):
                raise ValueError('Processing component has an incompatible input contract')
            if (recipe.limits.max_bytes > descriptor.max_bytes
                or recipe.limits.max_pages > descriptor.max_pages
                or recipe.limits.timeout_seconds > descriptor.timeout_seconds):
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Recipe exceeds the selected component limits')
            for pin in descriptor.libraries:
                if pin.name in libraries and libraries[pin.name] != pin:
                    raise ValueError('Processing components require incompatible library versions')
                libraries[pin.name] = pin
        if recipe.ocr is not None and not self._components[('processor', recipe.processor.name, recipe.processor.version)].supports_ocr:
            raise ValueError('Selected processor does not support OCR composition')
        expected = tuple(sorted(libraries.values(), key=lambda pin: pin.name))
        if recipe.libraries and set(recipe.libraries) != set(expected):
            raise ValueError('Recipe library pins do not match the registered components')
        return recipe.model_copy(update={'libraries': expected})

    def readiness(self, recipe: ProcessingRecipe, *, content_type: str | None = None, model_binding_ready=False):
        recipe = self.normalize(recipe)
        diagnostics = []
        if recipe.model is not None and not model_binding_ready:
            diagnostics.append('model_binding_not_verified')
        for role in ('processor', 'indexer', 'ocr', 'enricher'):
            selected = getattr(recipe, role)
            if selected is None:
                continue
            descriptor = self._components[(role, selected.name, selected.version)]
            if not descriptor.available:
                diagnostics.append(f'{role}:{selected.name}:{descriptor.diagnostic}')
            if (content_type is not None and role in {'processor', 'ocr'}
                and content_type.split(';', 1)[0].lower().strip() not in descriptor.media_types):
                diagnostics.append(f'{role}:{selected.name}:unsupported_media_type')
        return {'ready': not diagnostics, 'diagnostics': tuple(diagnostics), 'mode': recipe.mode}

    def capabilities(self):
        return tuple({'name': item.name, 'version': item.version, 'role': item.role,
                      'ready': item.available, 'diagnostic': None if item.available else item.diagnostic,
                      'media_types': sorted(item.media_types) if item.available else [],
                      'input_kind': item.input_kind, 'output_kind': item.output_kind,
                      'max_bytes': item.max_bytes, 'max_pages': item.max_pages,
                      'timeout_seconds': item.timeout_seconds}
                     for item in sorted(self._components.values(), key=lambda value: (value.role, value.name, value.version)))


def processing_fingerprint(*, sha256: str, size_bytes: int, content_type: str, recipe: ProcessingRecipe):
    sha256_digest(sha256)
    if type(size_bytes) is not int or size_bytes < 0:
        raise ValueError('Processing identity requires a nonnegative source size')
    payload = {'source_sha256': sha256, 'size_bytes': size_bytes,
               'content_type': content_type, 'recipe_fingerprint': recipe.fingerprint()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
