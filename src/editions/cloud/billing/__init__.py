from __future__ import annotations

import sys

# Billing is a Woobe Cloud edition package. Register the previous import namespace
# while the pre-public codebase is migrated so internal absolute imports continue
# resolving to this package without duplicating the implementation.
sys.modules["modules.billing"] = sys.modules[__name__]

from editions.cloud.billing.presentation import routes
from editions.cloud.billing.infra.workers import registry

__all__ = [
    "routes",
    "registry",
]
