"""Native Package execution capability; worker lifecycle belongs to the host."""

from modules.package.composition.services import build_package_executor

__all__ = ["build_package_executor"]

