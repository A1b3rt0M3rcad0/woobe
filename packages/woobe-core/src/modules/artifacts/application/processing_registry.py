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
    languages: tuple[str, ...] = ()
    default_languages: tuple[str, ...] = ()

    def __post_init__(self):
        ComponentReference(name=self.name, version=self.version)
        if self.role not in {'processor', 'indexer', 'ocr', 'enricher'}:
            raise ValueError('Unknown processing component role')
        expected = {'processor': 'canonical', 'ocr': 'canonical', 'indexer': 'index', 'enricher': 'enrichment'}
        if self.output_kind != expected[self.role]:
            raise ValueError('Processing component has an incompatible output contract')
        if min(self.max_bytes, self.max_pages, self.timeout_seconds) < 1:
            raise ValueError('Component limits must be positive')
        if any(language not in self.languages for language in self.default_languages):
            raise ValueError('Default processing languages must be supported')


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
                or (role in {'indexer', 'enricher'} and descriptor.input_kind not in {'original', 'canonical', 'index'})):
                raise ValueError('Processing component has an incompatible input contract')
            if (recipe.limits.max_bytes > descriptor.max_bytes
                or recipe.limits.max_pages > descriptor.max_pages
                or recipe.limits.timeout_seconds > descriptor.timeout_seconds):
                fallback_ready = (role == 'indexer' and recipe.parameters.indexer_fallback == 'structural'
                    and self._components.get(('indexer', 'structural', '1')) is not None
                    and self._components[('indexer', 'structural', '1')].available)
                if not fallback_ready:
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
        parameters = recipe.parameters
        if recipe.ocr is not None and not parameters.languages:
            defaults = self._components[('ocr', recipe.ocr.name, recipe.ocr.version)].default_languages
            parameters = parameters.model_copy(update={'languages': defaults})
        return recipe.model_copy(update={'libraries': expected, 'parameters': parameters})

    def readiness(self, recipe: ProcessingRecipe, *, content_type: str | None = None, model_binding_ready=False):
        recipe = self.normalize(recipe)
        diagnostics = []
        notes = []
        if recipe.model is not None and not model_binding_ready:
            diagnostics.append('model_binding_not_verified')
        if recipe.ocr is not None:
            descriptor = self._components[('ocr', recipe.ocr.name, recipe.ocr.version)]
            if any(language not in descriptor.languages for language in recipe.parameters.languages):
                diagnostics.append('ocr:unsupported_language')
        for role in ('processor', 'indexer', 'ocr', 'enricher'):
            selected = getattr(recipe, role)
            if selected is None:
                continue
            descriptor = self._components[(role, selected.name, selected.version)]
            fallback_ready = (role == 'indexer' and recipe.parameters.indexer_fallback == 'structural'
                and self._components.get(('indexer', 'structural', '1')) is not None
                and self._components[('indexer', 'structural', '1')].available)
            if not descriptor.available and not fallback_ready:
                diagnostics.append(f'{role}:{selected.name}:{descriptor.diagnostic}')
            elif not descriptor.available and fallback_ready:
                notes.append(f'{role}:{selected.name}:{descriptor.diagnostic}:structural_fallback')
            if (content_type is not None and role in {'processor', 'ocr'}
                and content_type.split(';', 1)[0].lower().strip() not in descriptor.media_types):
                diagnostics.append(f'{role}:{selected.name}:unsupported_media_type')
            if (content_type is not None and role == 'indexer' and descriptor.media_types
                and content_type.split(';', 1)[0].lower().strip() not in descriptor.media_types
                and recipe.parameters.indexer_fallback != 'structural'):
                diagnostics.append(f'{role}:{selected.name}:unsupported_media_type')
            elif (content_type is not None and role == 'indexer' and descriptor.media_types
                and content_type.split(';', 1)[0].lower().strip() not in descriptor.media_types
                and recipe.parameters.indexer_fallback == 'structural'):
                notes.append(f'{role}:{selected.name}:unsupported_media_type:structural_fallback')
        return {'ready': not diagnostics, 'diagnostics': tuple((*diagnostics, *notes)), 'mode': recipe.mode}

    def capabilities(self):
        return tuple({'name': item.name, 'version': item.version, 'role': item.role,
                      'ready': item.available, 'diagnostic': None if item.available else item.diagnostic,
                      'media_types': sorted(item.media_types) if item.available else [],
                      'input_kind': item.input_kind, 'output_kind': item.output_kind,
                      'max_bytes': item.max_bytes, 'max_pages': item.max_pages,
                      'timeout_seconds': item.timeout_seconds, 'languages': list(item.languages) if item.available else [],
                      'default_languages': list(item.default_languages) if item.available else []}
                     for item in sorted(self._components.values(), key=lambda value: (value.role, value.name, value.version)))


def processing_fingerprint(*, sha256: str, size_bytes: int, content_type: str, recipe: ProcessingRecipe, model_binding_fingerprint: str | None = None):
    sha256_digest(sha256)
    if type(size_bytes) is not int or size_bytes < 0:
        raise ValueError('Processing identity requires a nonnegative source size')
    payload = {'source_sha256': sha256, 'size_bytes': size_bytes,
               'content_type': content_type, 'recipe_fingerprint': recipe.fingerprint()}
    if recipe.mode != 'store_only':
        payload['representation_format_version'] = '1'
    if recipe.model is not None:
        if model_binding_fingerprint is None:
            raise ValueError('Modeled processing requires its frozen scoped binding fingerprint')
        sha256_digest(model_binding_fingerprint)
        payload['model_binding_fingerprint'] = model_binding_fingerprint
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
