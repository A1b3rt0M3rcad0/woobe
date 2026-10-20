from importlib.metadata import version
import platform

from modules.artifacts.application.contracts.processing import LibraryPin
from modules.artifacts.application.processing_registry import ComponentDescriptor
from modules.artifacts.infra.processing.docling_manifest import docling_readiness


MEDIA_TYPES = frozenset({'text/plain', 'text/markdown', 'text/x-markdown', 'application/json', 'text/json', 'text/csv', 'application/csv'})
PDFIUM_VERSION = '156.0.8076.0'


def native_text_descriptor():
    return ComponentDescriptor('native-text', '1', 'processor', 'original', 'canonical', MEDIA_TYPES,
        libraries=(LibraryPin(name='python', version=platform.python_version()),
                   LibraryPin(name='markdown-it-py', version=version('markdown-it-py')),
                   LibraryPin(name='mdurl', version=version('mdurl'))),
        available=True, diagnostic='')


def native_pdf_descriptor():
    return ComponentDescriptor('native-pdf', '1', 'processor', 'original', 'canonical', frozenset({'application/pdf'}),
        libraries=(LibraryPin(name='python', version=platform.python_version()),
                   LibraryPin(name='pypdf', version=version('pypdf')),
                   LibraryPin(name='pypdfium2', version=version('pypdfium2')),
                   LibraryPin(name='pdfium', version=PDFIUM_VERSION),
                   LibraryPin(name='Pillow', version=version('Pillow'))),
        available=platform.system() == 'Linux', diagnostic='' if platform.system() == 'Linux' else 'isolated_worker_requires_linux')


def docling_native_descriptor():
    ready, diagnostic, manifest, digest = docling_readiness()
    ready = ready and platform.system() == 'Linux'
    libraries = tuple(LibraryPin(name=name, version=version) for name, version in manifest['libraries'].items())
    return ComponentDescriptor('docling-native', '2.140.0', 'processor', 'original', 'canonical',
        frozenset({'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}),
        libraries=(*native_pdf_descriptor().libraries, *libraries, LibraryPin(name='docling-native-manifest', version=digest)),
        available=ready, diagnostic=diagnostic or ('' if ready else 'isolated_worker_requires_linux'))
