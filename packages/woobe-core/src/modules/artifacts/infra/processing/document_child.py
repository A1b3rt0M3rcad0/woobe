import json
from pathlib import Path
import resource
import socket
import sys


def main(directory):
    root = Path(directory)
    command = json.loads((root / 'command.json').read_bytes())
    timeout = command['recipe']['limits']['timeout_seconds']
    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 1))
    resource.setrlimit(resource.RLIMIT_AS, (command['memory_bytes'], command['memory_bytes']))
    resource.setrlimit(resource.RLIMIT_FSIZE, (536_870_912, 536_870_912))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    from modules.artifacts.application.contracts.processing import ProcessingRecipe
    from modules.artifacts.application.document_codec import canonical_value, json_chunks
    from modules.artifacts.domain.models import ArtifactError, Revision
    try:
        def deny_network(*args, **kwargs):
            raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Offline image/OCR processing cannot access the network')
        socket.socket.connect = deny_network
        socket.socket.connect_ex = deny_network
        socket.create_connection = deny_network
        from modules.artifacts.infra.processing.document_engine import process_document
        recipe = ProcessingRecipe.model_validate(command['recipe'])
        revision = Revision(**command['revision'])
        result = process_document(root, revision, recipe,
            executable=command['tesseract_executable'], directory=command['ocr_data_dir'])
        with (root / 'output').open('wb') as output:
            for chunk in json_chunks(canonical_value(result)):
                output.write(chunk)
    except ArtifactError as error:
        (root / 'error.json').write_text(json.dumps({'code': str(error.code), 'message': str(error)}))
        return 2
    except Exception:
        (root / 'error.json').write_text(json.dumps({'code': 'DOCUMENT_CONVERSION_FAILED', 'message': 'Native visual/OCR processing failed'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
