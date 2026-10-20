import json
from pathlib import Path
import resource
import socket
import sys


def main(directory):
    root = Path(directory)
    command = json.loads((root / 'command.json').read_bytes())
    timeout = command['recipe']['limits']['timeout_seconds']
    memory = command['memory_bytes']
    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 1))
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_FSIZE, (536_870_912, 536_870_912))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    from modules.artifacts.application.contracts.processing import ProcessingRecipe
    from modules.artifacts.application.document_codec import canonical_value, json_chunks
    from modules.artifacts.domain.models import ArtifactError, Revision
    from modules.artifacts.infra.processing.docling_manifest import docling_readiness
    try:
        ready, diagnostic, manifest, digest = docling_readiness()
        if not ready:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Optional Docling dependencies are missing or incompatible')
        if command['operation'] != 'extract' or command['source_name'] not in {'source.pdf', 'source.docx'}:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Unsupported Docling operation')

        def deny_network(*args, **kwargs):
            raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Offline document conversion cannot access the network')

        # Scoped to this single-use child; no other request or tenant shares it.
        socket.socket.connect = deny_network
        socket.socket.connect_ex = deny_network
        socket.create_connection = deny_network
        from modules.artifacts.infra.processing.docling_engine import convert_docling
        recipe = ProcessingRecipe.model_validate(command['recipe'])
        if recipe.libraries:
            pins = {pin.name: pin.version for pin in recipe.libraries}
            if (pins.get('docling-native-manifest') != digest
                or any(pins.get(name) != expected for name, expected in manifest['libraries'].items())):
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Pinned Docling recipe differs from the installed conversion manifest')
        revision = Revision(**command['revision'])
        document = convert_docling(root / command['source_name'], revision, recipe, threads=command['threads'])
        with (root / 'output').open('wb') as output:
            for chunk in json_chunks(canonical_value(document)):
                output.write(chunk)
    except ArtifactError as error:
        (root / 'error.json').write_text(json.dumps({'code': str(error.code), 'message': str(error)}))
        return 2
    except Exception:
        (root / 'error.json').write_text(json.dumps({'code': 'DOCUMENT_CONVERSION_FAILED', 'message': 'Docling conversion failed'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
