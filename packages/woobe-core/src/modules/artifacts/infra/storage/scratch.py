from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.artifacts.domain.models import opaque_id


@contextmanager
def artifact_scratch(operation_id: str):
    """Worker adapters use this inside their blocking processing boundary."""
    opaque_id(operation_id)
    with TemporaryDirectory(prefix=f'woobe-artifacts-{operation_id}-') as directory:
        yield Path(directory)
