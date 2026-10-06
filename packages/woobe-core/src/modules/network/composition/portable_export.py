from modules.agent.entrypoint import build_portable_agent_export_reader
from modules.network.composition.resources import SESSION_FACTORY
from modules.network.composition.services import build_network_service
from modules.network.infra.services.portable_export import PortableNetworkExportReader


def build_portable_network_export_reader() -> PortableNetworkExportReader:
    return PortableNetworkExportReader(
        SESSION_FACTORY, build_network_service(), build_portable_agent_export_reader()
    )
