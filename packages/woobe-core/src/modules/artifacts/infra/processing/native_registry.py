from importlib.metadata import version
import platform

from modules.artifacts.application.contracts.processing import LibraryPin
from modules.artifacts.application.processing_registry import ComponentDescriptor


MEDIA_TYPES = frozenset({'text/plain', 'text/markdown', 'text/x-markdown', 'application/json', 'text/json', 'text/csv', 'application/csv'})


def native_text_descriptor():
    return ComponentDescriptor('native-text', '1', 'processor', 'original', 'canonical', MEDIA_TYPES,
        libraries=(LibraryPin(name='python', version=platform.python_version()),
                   LibraryPin(name='markdown-it-py', version=version('markdown-it-py')),
                   LibraryPin(name='mdurl', version=version('mdurl'))),
        available=True, diagnostic='')
