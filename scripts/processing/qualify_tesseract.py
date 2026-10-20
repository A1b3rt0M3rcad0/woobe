"""Verify the actual local engine and pinned language files, then record readiness."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packages/woobe-core/src'))

from modules.artifacts.infra.processing.ocr_manifest import RECEIPT, qualify_installation  # noqa: E402


def qualify(directory, executable):
    receipt = qualify_installation(directory, executable)
    root = Path(directory).resolve()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix='.ocr-receipt-', mode='w', delete=False) as target:
            temporary = Path(target.name)
            json.dump(receipt, target, sort_keys=True)
            target.flush()
            os.fsync(target.fileno())
        temporary.replace(root / RECEIPT)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print('Qualified Tesseract ' + receipt['engine_version'] + ' with pinned eng/por/osd artifacts')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--executable', default='/usr/bin/tesseract')
    args = parser.parse_args()
    qualify(args.directory, args.executable)
