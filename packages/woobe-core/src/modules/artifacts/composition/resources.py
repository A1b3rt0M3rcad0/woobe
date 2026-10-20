from modules.artifacts.application.processing_registry import ProcessingRegistry
from modules.artifacts.infra.processing.native_registry import native_pdf_descriptor, native_text_descriptor
from shared.composition_resources import DATABASE_ENGINE as DATABASE_ENGINE, SETTINGS as SETTINGS

# Configured profile membership is distinct from live I/O readiness, which is
# checked by the operation/capability probe. Local needs a shared volume at scale.
STORAGE_PROFILES = frozenset({'local', 's3'} if SETTINGS.s3_bucket else {'local'})

PROCESSING_REGISTRY = ProcessingRegistry((native_text_descriptor(), native_pdf_descriptor()))
