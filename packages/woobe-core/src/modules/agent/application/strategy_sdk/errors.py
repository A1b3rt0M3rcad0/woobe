from __future__ import annotations


class StrategyExecutionError(RuntimeError):
    """Runtime mechanism failure exposed to an Execution Strategy.

    The Strategy sees only this stable algorithm-facing error. Strategy Runtime
    restores the underlying runtime/instrumentation error when the failure leaves
    the Strategy boundary unhandled.
    """


__all__ = ["StrategyExecutionError"]
