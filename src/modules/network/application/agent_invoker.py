"""Compatibility import for the canonical Network Agent runtime adapter.

Evaluation originally imported the invoker from the application package. The
implementation is owned by ``modules.network.infra.runtime``; keeping this
module small preserves the public import while existing callers migrate to the
canonical package.
"""

from modules.network.infra.runtime import ProjectRAIAgentInvoker

__all__ = ["ProjectRAIAgentInvoker"]
