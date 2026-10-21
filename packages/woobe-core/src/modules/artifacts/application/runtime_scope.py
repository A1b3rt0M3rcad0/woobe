"""Run-bound Artifact requests that cannot choose another Workspace or catalog."""

from modules.artifacts.application.contracts.files import ListFiles, ReadFile, WriteBytes
from modules.artifacts.application.contracts.representations import (
    ReadSource, SourceReadDefinition,
)
from modules.artifacts.application.contracts.search import SearchDocuments
from modules.artifacts.domain.models import Action, ArtifactError, RuntimeArtifactBinding, opaque_id


class RunArtifactContext:
    def __init__(self, principal, binding: RuntimeArtifactBinding, run_id: str,
                 *, output_node_ids: frozenset[str] = frozenset()):
        opaque_id(run_id)
        for node_id in output_node_ids:
            opaque_id(node_id)
        self._principal = principal
        self.binding = binding
        self.run_id = run_id
        self.output_node_ids = output_node_ids

    def _require(self, action: Action):
        if action not in self.binding.actions:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Run does not have this Artifact capability')

    def list_files(self, *, directory='', limit=50, cursor=None):
        self._require(Action.READ)
        return ListFiles(self._principal, self.binding.scope, self.binding.workspace_id,
            directory=directory, limit=limit, cursor=cursor,
            catalog_version=self.binding.catalog_version)

    def search(self, query, *, mode='text', limit=20, cursor=None):
        self._require(Action.SEARCH)
        return SearchDocuments(self._principal, self.binding.scope, self.binding.workspace_id,
            query=query, mode=mode, limit=limit, cursor=cursor,
            catalog_version=self.binding.catalog_version, run_id=self.run_id)

    def read_file(self, artifact_id, revision_id):
        self._require(Action.READ)
        return ReadFile(self._principal, self.binding.scope, self.binding.workspace_id,
            artifact_id, revision_id, run_id=self.run_id,
            output_node_ids=self.output_node_ids,
            catalog_version=self.binding.catalog_version)

    def transfer_file(self, artifact_id, revision_id):
        self._require(Action.TRANSFER)
        # Transfer always reuses the normal exact-revision read authorization too.
        return self.read_file(artifact_id, revision_id)

    def write_external_output(
        self, *, operation_id, path, content, content_type, producer_id,
        external_operation_ref=None, source_refs=(),
    ):
        self._require(Action.WRITE)
        return WriteBytes(
            self._principal,
            self.binding.scope,
            self.binding.workspace_id,
            operation_id,
            path,
            content,
            content_type,
            producer_id,
            external_operation_ref,
            tuple(source_refs),
            self.run_id,
            next(iter(self.output_node_ids), None),
        )

    def read_output(self, artifact_id, revision_id):
        """Read a previously returned exact output ref from this Run/authorized Nodes."""
        self._require(Action.READ)
        return ReadFile(self._principal, self.binding.scope, self.binding.workspace_id,
            artifact_id, revision_id, run_id=self.run_id, output_node_ids=self.output_node_ids,
            catalog_version=self.binding.catalog_version)

    def read_source(self, definition: SourceReadDefinition):
        self._require(Action.READ)
        return ReadSource(self._principal, self.binding.scope, self.binding.workspace_id,
            definition, run_id=self.run_id, catalog_version=self.binding.catalog_version,
            output_node_ids=self.output_node_ids)
