from modules.agent.domain.release_snapshot import release_snapshot_hash
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.release_activation_repository import AgentReleaseActivationModel
from shared.infra.asac_history_reader import ASaCHistoryReader


class AgentHistoryReader(ASaCHistoryReader):
    def __init__(self, sessions, owner, cursor_key):
        super().__init__(
        sessions, cursor_key=cursor_key, kind="Agent", root=AgentModel, release=AgentReleaseModel,
        activation=AgentReleaseActivationModel, owner=owner,
        resource_column="agent_id", release_kind=("snapshot_kind", "release"),
        render_release=lambda row: {"snapshot_id": str(row.id), "version": row.version,
                                    "runtime_digest": "sha256:" + release_snapshot_hash(row),
                                    "runtime_digest_scope": "native-agent-snapshot@legacy", "parents": []},
        render_activation=lambda row: {"release_id": str(row.release_id),
                                       "previous_release_id": str(row.previous_release_id) if row.previous_release_id else None,
                                       "action": row.action, "reason": row.change_description},
    )
