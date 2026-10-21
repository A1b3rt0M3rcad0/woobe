"""Package 2.0 configuration intent. The 1.0 catalog remains unchanged."""
from typing import Literal

from pydantic import ConfigDict, Field, create_model, model_validator

from modules.package.application.dtos import (
    DOCUMENT_MODELS, StrictDTO, PackageManifestV1, PackageSpec, Ref,
    AgentSpecV1, AgentDocument, NetworkSettings, NetworkSpecV1, NetworkDocument,
    ImportBindingsV1, KnowledgeBinding, PortableCredentialMetadata, ToolSpecV1, ToolDocument,
    NetworkNode,
)
from modules.agent.contract_boundary import HttpToolConfig, HttpRouteConfig, McpToolConfig
from shared.contracts.artifact_capability import ArtifactCapability
from shared.contracts.project_configuration import compile_authentication


class ConfigurationKeyDefinition(StrictDTO):
    key: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    kind: Literal["value", "secret"] = "secret"
    description: str = Field(default="", max_length=2048)
    value_format: Literal["string", "token", "json", "pem", "url"] = "token"
    validation_rules: dict = Field(default_factory=dict)


class RemoteConfigurationReference(StrictDTO):
    source: Literal["project_environment"]
    key: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


class ProviderAuthentication(StrictDTO):
    type: Literal["api_key"]
    fields: dict[str, RemoteConfigurationReference]

    @model_validator(mode="after")
    def valid_fields(self):
        compile_authentication(self.model_dump())
        return self


class ToolAuthentication(StrictDTO):
    type: Literal["api_key", "bearer", "basic", "headers", "none"]
    fields: dict[str, RemoteConfigurationReference] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_fields(self):
        compile_authentication(self.model_dump(exclude_none=True), allow_none=True)
        return self


class HttpRouteConfigV2(HttpRouteConfig):
    authentication: ToolAuthentication | None = None


class HttpToolConfigV2(HttpToolConfig):
    authentication: ToolAuthentication
    auth: None = None
    routes: list[HttpRouteConfigV2] = Field(default_factory=list)


class McpToolConfigV2(McpToolConfig):
    authentication: ToolAuthentication
    oauth: None = None


class ToolSpecV2(ToolSpecV1):
    config: HttpToolConfigV2 | McpToolConfigV2


class ToolDocumentV2(ToolDocument):
    schema_version: Literal["2.0"]
    spec: ToolSpecV2


class AgentSpecV2(AgentSpecV1):
    artifacts: ArtifactCapability = Field(default_factory=ArtifactCapability)
    knowledge_strategy: Literal["rag", "none"] | None = None


class AgentDocumentV2(AgentDocument):
    schema_version: Literal["2.0"]
    spec: AgentSpecV2


class NetworkArtifactWorkspaceBindingV2(StrictDTO):
    field: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    namespace: str = Field(min_length=1, max_length=255)
    scope: Literal["run", "session"]
    actions: list[Literal["read", "search", "write", "delete", "process", "transfer"]] = Field(
        default_factory=lambda: ["read", "search"], min_length=1, max_length=6
    )


class NetworkNodeV2(NetworkNode):
    artifact_actions: list[
        Literal["read", "search", "write", "delete", "process", "transfer"]
    ] = Field(default_factory=list, max_length=6)


class NetworkSettingsV2(NetworkSettings):
    artifacts_enabled: bool = False
    artifact_workspace_binding: NetworkArtifactWorkspaceBindingV2 | None = None

    @model_validator(mode="after")
    def valid_artifact_binding(self):
        if self.artifacts_enabled != (self.artifact_workspace_binding is not None):
            raise ValueError("Enabled Network Artifacts require a Workspace binding")
        if self.artifact_workspace_binding is not None and len(
            set(self.artifact_workspace_binding.actions)
        ) != len(self.artifact_workspace_binding.actions):
            raise ValueError("Network artifact actions must be unique")
        return self


class NetworkSpecV2(NetworkSpecV1):
    nodes: list[NetworkNodeV2] = Field(min_length=1)
    settings: NetworkSettingsV2 = Field(default_factory=NetworkSettingsV2)

    @model_validator(mode="after")
    def nodes_within_artifact_policy(self):
        policy = self.settings.artifact_workspace_binding
        if policy is None:
            if any(node.artifact_actions for node in self.nodes):
                raise ValueError("Network Node artifact actions require Network Artifacts")
            return self
        allowed = set(policy.actions)
        if any(not set(node.artifact_actions) <= allowed for node in self.nodes):
            raise ValueError("Network Node artifact actions exceed the Network policy")
        return self


class NetworkDocumentV2(NetworkDocument):
    schema_version: Literal["2.0"]
    spec: NetworkSpecV2


class ProviderConnectionDefinition(StrictDTO):
    provider: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    metadata: PortableCredentialMetadata | None = None
    authentication: ProviderAuthentication


class ConfigurationDeclarations(StrictDTO):
    keys: list[ConfigurationKeyDefinition] = Field(default_factory=list, max_length=1000)


class StructuralRequirements(StrictDTO):
    knowledge: list[Ref] = Field(default_factory=list)


class PackageSpecV2(PackageSpec):
    configuration: ConfigurationDeclarations = Field(default_factory=ConfigurationDeclarations)
    connections: dict[str, ProviderConnectionDefinition] = Field(default_factory=dict)
    requires: StructuralRequirements = Field(default_factory=StructuralRequirements)


class PackageManifestV2(PackageManifestV1):
    schema_version: Literal["2.0"]
    spec: PackageSpecV2


class ConfigurationKeyBinding(StrictDTO):
    """Reuse must be an explicit destination choice, never name-based adoption."""
    existing_key: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    create: bool = False
    model_config = ConfigDict(json_schema_extra={"oneOf": [
        {"required": ["existing_key"], "properties": {"existing_key": {"type": "string"}, "create": {"const": False}}},
        {"required": ["create"], "properties": {"create": {"const": True}, "existing_key": {"type": "null"}}},
    ]})

    @model_validator(mode="after")
    def source(self):
        if (self.existing_key is not None) == self.create:
            raise ValueError("Choose exactly one configuration destination")
        return self


class ProviderConnectionBinding(StrictDTO):
    credential_id: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    create: bool = False
    model_config = ConfigDict(json_schema_extra={"oneOf": [
        {"required": ["credential_id"], "properties": {"credential_id": {"type": "string"}, "create": {"const": False}}},
        {"required": ["create"], "properties": {"create": {"const": True}, "credential_id": {"type": "null"}}},
    ]})

    @model_validator(mode="after")
    def source(self):
        if (self.credential_id is not None) == self.create:
            raise ValueError("Choose exactly one connection destination")
        return self


class StructuralBindingsSpec(StrictDTO):
    credentials: dict[str, ProviderConnectionBinding] = Field(default_factory=dict)
    project_environment: dict[str, ConfigurationKeyBinding] = Field(default_factory=dict)
    knowledge: dict[str, KnowledgeBinding] = Field(default_factory=dict)


class ImportBindingsV2(ImportBindingsV1):
    schema_version: Literal["2.0"]
    spec: StructuralBindingsSpec


# Resource definitions keep their established shapes; the package version
# selects an explicit catalog. Never relax the frozen v1 models or catalog.
DOCUMENT_MODELS_V2 = {
    kind: create_model(model.__name__ + "V2", __base__=model, schema_version=(Literal["2.0"], ...))
    for kind, model in DOCUMENT_MODELS.items()
}
DOCUMENT_MODELS_V2.update(
    Package=PackageManifestV2,
    ImportBindings=ImportBindingsV2,
    Tool=ToolDocumentV2,
    Agent=AgentDocumentV2,
    Network=NetworkDocumentV2,
)
