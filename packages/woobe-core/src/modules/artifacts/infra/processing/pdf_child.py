"""Private subprocess entry: no Settings, provider credentials or API host."""
import json
from pathlib import Path
import resource
import sys


def main(directory):
    root = Path(directory)
    command = json.loads((root / 'command.json').read_bytes())
    timeout = command['recipe']['limits']['timeout_seconds']
    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 1))
    resource.setrlimit(resource.RLIMIT_AS, (1_610_612_736, 1_610_612_736))
    resource.setrlimit(resource.RLIMIT_FSIZE, (536_870_912, 536_870_912))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    from modules.artifacts.application.contracts.processing import ProcessingRecipe
    from modules.artifacts.application.document_codec import canonical_value, json_chunks
    from modules.artifacts.domain.models import ArtifactError, Revision
    from modules.artifacts.infra.processing.pdf_engine import extract_pdf, render_pdf
    try:
        recipe = ProcessingRecipe.model_validate(command['recipe'])
        revision = Revision(**command['revision'])
        if command['operation'] == 'extract':
            document = extract_pdf(str(root / 'source.pdf'), revision, recipe)
            with (root / 'output').open('wb') as output:
                for chunk in json_chunks(canonical_value(document)):
                    output.write(chunk)
        elif command['operation'] == 'render':
            content = render_pdf(str(root / 'source.pdf'), page_index=command['page_index'],
                max_pages=recipe.limits.max_pages, dpi=command['dpi'], max_pixels=command['max_pixels'])
            (root / 'output').write_bytes(content)
        else:
            raise ValueError('Invalid PDF subprocess operation')
    except ArtifactError as error:
        (root / 'error.json').write_text(json.dumps({'code': str(error.code), 'message': str(error)}))
        return 2
    except Exception:
        (root / 'error.json').write_text(json.dumps({'code': 'PDF_INVALID_DOCUMENT', 'message': 'PDF parsing or rendering failed'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
