"""Worker-facing boundary; no processing capability is advertised before wiring."""

from modules.artifacts.composition.public_api import CONTRACT_VERSION as CONTRACT_VERSION

from modules.artifacts.composition.processing import build_processing_runner as build_processing_runner
