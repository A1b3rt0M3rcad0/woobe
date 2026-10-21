"""Check base startup without PageIndex-only packages and the opt-in profile."""
import sys

import modules.artifacts.entrypoint  # noqa: F401
from modules.artifacts.composition.resources import PROCESSING_REGISTRY


def main():
    available = '--available' in sys.argv[1:]
    descriptor = next(item for item in PROCESSING_REGISTRY.capabilities()
        if item['name'] == 'pageindex-flash')
    if available:
        assert descriptor['ready'], descriptor
        assert descriptor['diagnostic'] is None, descriptor
    else:
        assert not descriptor['ready'], descriptor
        assert descriptor['diagnostic'] == 'pageindex_local_extra_not_installed', descriptor
    print('PageIndex optional profile is ready' if available else 'Base startup succeeded without PageIndex extra')


if __name__ == '__main__':
    main()
