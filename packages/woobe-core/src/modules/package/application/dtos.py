from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from modules.agent.contract_boundary import (
    PortableCredentialMetadata,
    ToolInputBinding,
    BehaviorSpecification,
    ContextPolicyV1,
    HttpToolConfig,
    McpToolConfig,
    RAGBuildConfig,
    RAGRuntimeConfig,
)


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Metadata(StrictDTO):
    key: str = Field(
        min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$"
    )
    name: str = Field(min_length=1, max_length=255)
    version: str | None = None
    description: str = ""


class PackageMetadata(StrictDTO):
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=64)
    description: str = ""


class Ref(StrictDTO):
    ref: str = Field(min_length=1, max_length=128)


class Entrypoint(Ref):
    kind: Literal["Agent", "Network"]


class CredentialRequirement(Ref):
    provider: str
    metadata: PortableCredentialMetadata | None = None


class EnvironmentRequirement(StrictDTO):
    key: str
    kind: Literal["value", "secret"]


class Requirements(StrictDTO):
    credentials: list[CredentialRequirement] = Field(default_factory=list)
    project_environment: list[EnvironmentRequirement] = Field(default_factory=list)
    secrets: list[Ref] = Field(default_factory=list)
    knowledge: list[Ref] = Field(default_factory=list)


class Integrity(StrictDTO):
    algorithm: Literal["sha256"] = "sha256"


class PackageSpec(StrictDTO):
    entrypoint: Entrypoint
    resources: list[str] = Field(min_length=1, max_length=1023)
    requires: Requirements = Field(default_factory=Requirements)
    integrity: Integrity = Field(default_factory=Integrity)


class Provenance(StrictDTO):
    source_release: dict[str, Any] | None = None
    exporter: str | None = None
    snapshot_schema_version: str | None = None


class Document(StrictDTO):
    format: Literal["woobe-package"]
    schema_version: Literal["1.0"]
    metadata: Metadata
    provenance: Provenance | None = None


class PackageManifestV1(StrictDTO):
    format: Literal["woobe-package"]
    schema_version: Literal["1.0"]
    kind: Literal["Package"]
    metadata: PackageMetadata
    spec: PackageSpec
    provenance: Provenance | None = None


class ModelSpecRefV1(StrictDTO):
    provider: str
    model: str
    credential: Ref
    model_type: str = "language"
    base_url: str | None = None
    model_spec_hint: dict[str, Any] | None = None


class ModelDocument(Document):
    kind: Literal["Model"]
    spec: ModelSpecRefV1


class ModelParameters(StrictDTO):
    temperature: float | None = None
    max_output_tokens: int | None = Field(default=None, ge=1)


class AgentModels(StrictDTO):
    primary: Ref
    fallback: Ref | None = None
    parameters: ModelParameters = Field(default_factory=ModelParameters)


class StrategySelection(StrictDTO):
    config_schema_version: str = "1"
    strategy: str
    config: dict[str, Any] = Field(default_factory=dict)


class ContextManager(StrictDTO):
    name: str


class AgentContext(StrictDTO):
    manager: ContextManager = Field(
        default_factory=lambda: ContextManager(name="stdcm")
    )
    policy: ContextPolicyV1 = Field(default_factory=ContextPolicyV1)


class AgentSession(StrictDTO):
    mode: Literal["stateful", "stateless"] = "stateless"


class SkillBinding(Ref):
    version: str
    enabled: bool = True


class AgentKnowledge(StrictDTO):
    strategy_config_schema_version: str = "1"
    strategy: str = "rag"
    strategy_config: dict[str, Any] = Field(default_factory=dict)
    source: Ref
    rag: RAGRuntimeConfig = Field(default_factory=RAGRuntimeConfig)


class AgentOutput(StrictDTO):
    contract_ref: str | None = None
    response_format: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


class ModelExposure(StrictDTO):
    expose: bool = False


class ExternalField(StrictDTO):
    schema_: dict[str, Any] = Field(alias="schema")
    scope: Literal["run", "session"] = "run"
    required: bool = False
    default: Any = None
    model: ModelExposure = Field(default_factory=ModelExposure)
    description: str = ""


class AgentSpecV1(StrictDTO):
    type: Literal["chat"] = "chat"
    behavior: BehaviorSpecification | None = None
    prompt_ref: str | None = None
    legacy_system_prompt: str | None = None
    model: AgentModels
    execution: StrategySelection = Field(
        default_factory=lambda: StrategySelection(strategy="standard")
    )
    context: AgentContext = Field(default_factory=AgentContext)
    session: AgentSession = Field(default_factory=AgentSession)
    tools: list[Ref] = Field(default_factory=list)
    skills: list[SkillBinding] = Field(default_factory=list)
    knowledge: AgentKnowledge | None = None
    output: AgentOutput | None = None
    external_context: dict[str, ExternalField] = Field(default_factory=dict)


class AgentDocument(Document):
    kind: Literal["Agent"]
    spec: AgentSpecV1


class NodeBinding(StrictDTO):
    source: Literal["draft", "staging", "release"] = "draft"


class NetworkNode(StrictDTO):
    key: str
    agent_ref: str
    label: str = ""
    capability_description: str = ""
    position: dict[str, float] = Field(default_factory=dict)
    binding: NodeBinding = Field(default_factory=NodeBinding)


class NetworkEdge(StrictDTO):
    from_: str = Field(alias="from")
    to: str


class NetworkSettings(StrictDTO):
    session_mode: Literal["stateful", "stateless"] = "stateless"
    max_depth: int = Field(default=4, ge=1)
    max_invocations: int = Field(default=16, ge=1)
    timeout_seconds: int = Field(default=90, ge=1)
    tool_result_max_chars: int = Field(default=16000, ge=1)


class NetworkSpecV1(StrictDTO):
    root: str
    nodes: list[NetworkNode] = Field(min_length=1)
    edges: list[NetworkEdge] = Field(default_factory=list)
    settings: NetworkSettings = Field(default_factory=NetworkSettings)


class NetworkDocument(Document):
    kind: Literal["Network"]
    spec: NetworkSpecV1


class McpPermission(StrictDTO):
    bindings: dict[str, ToolInputBinding] = Field(default_factory=dict)
    remote_name: str
    permission: Literal["allow", "deny", "review"]
    # Native MCP risk labels include unknown and user-defined classifications.
    risk: str | None = Field(default=None, min_length=1, max_length=256)


class ToolSpecV1(StrictDTO):
    type: Literal["http", "mcp"]
    description: str = ""
    timeout_ms: int = Field(default=10000, ge=1)
    config: HttpToolConfig | McpToolConfig
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    permission: Literal["allow", "deny", "review"] = "allow"
    risk: str | None = None
    permissions: list[McpPermission] = Field(default_factory=list)


class ToolDocument(Document):
    kind: Literal["Tool"]
    spec: ToolSpecV1


class SkillFiles(StrictDTO):
    manifest: str
    resources: list[str] = Field(default_factory=list)


class SkillDescriptorV1(StrictDTO):
    version: str
    package: SkillFiles
    required_tools: list[str] = Field(default_factory=list)


class SkillDocument(Document):
    kind: Literal["Skill"]
    spec: SkillDescriptorV1


class CollectionSpec(StrictDTO):
    name: str
    description: str = ""


class KnowledgeFile(StrictDTO):
    path: str
    title: str
    content_type: str | None = None


class EmbeddingSelection(StrictDTO):
    model_ref: str


class KnowledgeSpecV1(StrictDTO):
    mode: Literal["portable", "binding"]
    collection: CollectionSpec | None = None
    documents: list[KnowledgeFile] = Field(default_factory=list)
    embedding: EmbeddingSelection | None = None
    vector_snapshot: RAGBuildConfig | None = None
    binding: Ref | None = None


class KnowledgeDocument(Document):
    kind: Literal["Knowledge"]
    spec: KnowledgeSpecV1


class ContractSpecV1(StrictDTO):
    version: str
    validation_mode: Literal["strict", "lenient"] = "strict"
    repair_attempts: int = Field(default=0, ge=0)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    additional_instructions: str = ""


class ContractDocument(Document):
    kind: Literal["Contract"]
    spec: ContractSpecV1


class PromptSpecV1(StrictDTO):
    version: str
    content: str


class PromptDocument(Document):
    kind: Literal["Prompt"]
    spec: PromptSpecV1


def exclusive_binding_schema(existing_field):
    return {
        "oneOf": [
            {
                "required": [existing_field],
                "properties": {
                    existing_field: {"type": "string", "minLength": 1},
                    "protected_ref": {"type": "null"},
                },
            },
            {
                "required": ["protected_ref"],
                "properties": {
                    "protected_ref": {"type": "string", "minLength": 1},
                    existing_field: {"type": "null"},
                },
            },
        ]
    }


class CredentialBinding(StrictDTO):
    model_config = ConfigDict(
        json_schema_extra=exclusive_binding_schema("credential_id")
    )
    credential_id: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    protected_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=101,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$",
    )

    @model_validator(mode="after")
    def exclusive_source(self):
        if (self.credential_id is None) == (self.protected_ref is None):
            raise ValueError("Binding requires exactly one destination source")
        return self


class EnvironmentBinding(StrictDTO):
    model_config = ConfigDict(
        json_schema_extra=exclusive_binding_schema("existing_key")
    )
    existing_key: str | None = Field(default=None, min_length=1, max_length=128)
    protected_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=101,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$",
    )

    @model_validator(mode="after")
    def exclusive_source(self):
        if (self.existing_key is None) == (self.protected_ref is None):
            raise ValueError("Binding requires exactly one destination source")
        return self


class SecretBinding(EnvironmentBinding):
    pass


class KnowledgeBinding(StrictDTO):
    vector_snapshot_id: str


class BindingsSpec(StrictDTO):
    credentials: dict[str, CredentialBinding] = Field(default_factory=dict)
    project_environment: dict[str, EnvironmentBinding] = Field(default_factory=dict)
    secrets: dict[str, SecretBinding] = Field(default_factory=dict)
    knowledge: dict[str, KnowledgeBinding] = Field(default_factory=dict)


class BindingsMetadata(StrictDTO):
    name: str
    description: str = ""


class ImportBindingsV1(StrictDTO):
    format: Literal["woobe-package"]
    schema_version: Literal["1.0"]
    kind: Literal["ImportBindings"]
    metadata: BindingsMetadata
    spec: BindingsSpec


class InventoryFile(StrictDTO):
    path: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PackageLockV1(StrictDTO):
    format: Literal["woobe-package"]
    schema_version: Literal["1.0"]
    kind: Literal["PackageLock"]
    algorithm: Literal["sha256"]
    inventory: list[InventoryFile]
    artifact_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


DOCUMENT_MODELS = {
    "Package": PackageManifestV1,
    "Agent": AgentDocument,
    "Network": NetworkDocument,
    "Model": ModelDocument,
    "Tool": ToolDocument,
    "Skill": SkillDocument,
    "Knowledge": KnowledgeDocument,
    "Contract": ContractDocument,
    "Prompt": PromptDocument,
    "ImportBindings": ImportBindingsV1,
    "PackageLock": PackageLockV1,
}
