from modules.artifacts.composition.resources import PROCESSING_REGISTRY


def processing_component_capabilities():
    return PROCESSING_REGISTRY.capabilities()
