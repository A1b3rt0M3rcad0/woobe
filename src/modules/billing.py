"""Compatibility import for Billing after its move to the Woobe Cloud edition.

No Billing implementation lives in the shared core. New code must import
`editions.cloud.billing`; this module only keeps pre-public internal imports stable
while they are migrated.
"""

from __future__ import annotations

import importlib
import sys

_cloud_billing = importlib.import_module("editions.cloud.billing")
sys.modules[__name__] = _cloud_billing
