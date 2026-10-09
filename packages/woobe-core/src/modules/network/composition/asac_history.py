from modules.network.infra.database.asac_models import ASaCEnvironmentSelectionModel
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.database.schema_extensions import NetworkProductionActivationModel
from modules.network.infra.services.development_resource_reader import DevelopmentNetworkReader
from shared.composition_resources import SESSION_FACTORY, SETTINGS
from shared.infra.asac_history_reader import ASaCHistoryReader


def build_network_history_reader():
    return ASaCHistoryReader(
        SESSION_FACTORY, cursor_key=SETTINGS.secret_key, kind="Network", root=NetworkModel, release=NetworkVersionModel,
        activation=NetworkProductionActivationModel, owner=DevelopmentNetworkReader(), selections=ASaCEnvironmentSelectionModel,
        resource_column="network_id", release_kind=("kind", "release"),
        render_release=lambda row: {"snapshot_id": str(row.id), "version": row.version,
                                    "runtime_digest": "sha256:" + row.composition_hash,
                                    "runtime_digest_scope": "native-network-composition@legacy", "parents": []},
        render_activation=lambda row: {"release_id": str(row.version_id),
                                       "previous_release_id": str(row.previous_version_id) if row.previous_version_id else None,
                                       "action": row.activation_kind, "reason": row.change_description},
    )
