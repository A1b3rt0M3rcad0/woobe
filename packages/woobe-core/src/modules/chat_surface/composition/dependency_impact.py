from modules.chat_surface.composition.resources import SESSION_FACTORY
from modules.chat_surface.infra.database.dependency_impact_reader import (
    SurfaceDependencyImpactReader,
)


def build_surface_dependency_impact_reader():
    return SurfaceDependencyImpactReader(SESSION_FACTORY)
