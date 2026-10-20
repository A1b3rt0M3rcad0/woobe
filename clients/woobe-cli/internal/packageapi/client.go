// Package packageapi transports Package operations independently of Manifest.
package packageapi

import (
	"context"
	"encoding/json"
	"net/http"
	"regexp"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

var identifier = regexp.MustCompile(`^[A-Za-z0-9_.:-]{1,128}$`)
var uuidIdentifier = regexp.MustCompile(`^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$`)

// UUID paths accept either letter case; the server serializes UUID evidence in
// lowercase. Opaque IDs and idempotency keys keep their exact spelling.
func canonicalIdentifier(value string) string {
	if uuidIdentifier.MatchString(value) {
		return strings.ToLower(value)
	}
	return value
}

type Client struct {
	Control   *controlplane.Client
	ProjectID string
}

func New(control *controlplane.Client, project string) (*Client, error) {
	if control == nil || !identifier.MatchString(project) {
		return nil, output.New(2, "Package requires a destination project")
	}
	return &Client{Control: control, ProjectID: canonicalIdentifier(project)}, nil
}

func (c *Client) path(suffix string) string { return "/projects/" + c.ProjectID + "/packages" + suffix }

func (c *Client) request(ctx context.Context, method, suffix string, body any, destination any) error {
	return c.requestPath(ctx, method, c.path(suffix), body, destination)
}

func (c *Client) requestPath(ctx context.Context, method, path string, body any, destination any) error {
	var encoded []byte
	if body != nil {
		var err error
		encoded, err = json.Marshal(body)
		if err != nil || len(encoded) > 2<<20 {
			return output.New(2, "Package request is invalid or exceeds 2 MiB")
		}
	}
	value, _, err := c.Control.Request(ctx, method, path, nil, encoded)
	if err != nil {
		return err
	}
	envelope, ok := value.(map[string]any)
	if !ok || envelope["success"] != true {
		return output.New(9, "Server returned an invalid Package envelope")
	}
	data, ok := envelope["data"].(map[string]any)
	if !ok || (data["package_schema_version"] != "1.0" && data["package_schema_version"] != "2.0") {
		return output.New(9, "Server returned an unsupported Package schema")
	}
	encoded, err = json.Marshal(data)
	if err != nil || json.Unmarshal(encoded, destination) != nil {
		return output.New(9, "Server returned an invalid Package result")
	}
	return nil
}

type ASaCCapabilities struct {
	DefinitionDigestScopes     []string `json:"definition_digest_scopes"`
	AuthorSourceRetention      bool     `json:"author_source_retention"`
	RetainedObjectHydration    bool     `json:"retained_object_hydration"`
	RevisionCatalog            bool     `json:"revision_catalog"`
	AcceptedBindingGenerations bool     `json:"accepted_binding_generations"`
}

type Capabilities struct {
	SupportedSchemas       map[string]string `json:"supported_package_schemas"`
	StructuralInstallation bool              `json:"structural_installation"`
	ASaC                   ASaCCapabilities  `json:"asac"`
	PackageSchemaVersion   string            `json:"package_schema_version"`
	SchemaCatalogSHA256    string            `json:"schema_catalog_sha256"`
	SupportedOperations    []string          `json:"supported_operations"`
	PrincipalFingerprint   string            `json:"principal_fingerprint"`
}

func (c *Client) RequireSchema(ctx context.Context, version string, structural bool) error {
	if version == "1.0" && !structural {
		return nil
	}
	if packagefmt.VersionCatalogDigest(version) == "" {
		return output.New(9, "Unsupported Package schema")
	}
	caps, err := c.Capabilities(ctx)
	if err != nil {
		return err
	}
	if caps.SupportedSchemas[version] != packagefmt.VersionCatalogDigest(version) || (structural && !caps.StructuralInstallation) {
		return output.New(9, "Server does not advertise this Package schema and structural installation; update Woobe before retrying")
	}
	return nil
}

func (c *Client) Capabilities(ctx context.Context) (Capabilities, error) {
	var result Capabilities
	err := c.request(ctx, http.MethodGet, "/capabilities", nil, &result)
	return result, err
}

type InventoryItem struct {
	Component  string `json:"component,omitempty"`
	Kind       string `json:"kind,omitempty"`
	Action     string `json:"action,omitempty"`
	ResourceID string `json:"resource_id,omitempty"`
}
type Dependency struct {
	ID         string `json:"id,omitempty"`
	Code       string `json:"code,omitempty"`
	Component  string `json:"component,omitempty"`
	Kind       string `json:"kind,omitempty"`
	State      string `json:"state"`
	ResourceID string `json:"resource_id,omitempty"`
}
type Diagnostic struct {
	Code string `json:"code"`
	File string `json:"file,omitempty"`
	Path string `json:"path,omitempty"`
}
type Operation struct {
	InstallationMode         string          `json:"installation_mode,omitempty"`
	InstallationStatus       string          `json:"installation_status,omitempty"`
	ConfigurationStatus      string          `json:"configuration_status,omitempty"`
	RuntimePreparationStatus string          `json:"runtime_preparation_status,omitempty"`
	DeploymentStatus         string          `json:"deployment_status,omitempty"`
	PackageSchemaVersion     string          `json:"package_schema_version"`
	OperationID              string          `json:"operation_id"`
	ProjectID                string          `json:"project_id"`
	ArtifactDigest           string          `json:"artifact_digest"`
	State                    string          `json:"state"`
	Terminal                 bool            `json:"terminal"`
	Phase                    string          `json:"phase,omitempty"`
	PhasesCompleted          int64           `json:"phases_completed"`
	PhasesTotal              int64           `json:"phases_total"`
	Revision                 int64           `json:"revision"`
	NextPollAfterMS          int64           `json:"next_poll_after_ms,omitempty"`
	LifecycleState           string          `json:"lifecycle_state,omitempty"`
	ConfigurationReady       bool            `json:"configuration_ready"`
	ExecutionReady           bool            `json:"execution_ready"`
	Inventory                []InventoryItem `json:"inventory"`
	Dependencies             []Dependency    `json:"dependencies"`
	Diagnostics              []Diagnostic    `json:"diagnostics"`
}

func (c *Client) operation(ctx context.Context, method, suffix string, body any) (Operation, error) {
	var result Operation
	err := c.request(ctx, method, suffix, body, &result)
	if err != nil {
		return result, err
	}
	states := map[string]bool{"accepted": true, "resolving": true, "materializing": true, "verifying": true, "waiting_dependency": true, "succeeded": true, "failed": true, "cancelling": true, "cancelled": true}
	terminal := result.State == "succeeded" || result.State == "failed" || result.State == "cancelled"
	if !identifier.MatchString(result.OperationID) || result.ProjectID != c.ProjectID || !states[result.State] ||
		terminal != result.Terminal || result.Revision < 1 || result.PhasesCompleted < 0 || result.PhasesTotal < result.PhasesCompleted {
		return Operation{}, output.New(9, "Server returned inconsistent Package operation evidence")
	}
	return result, nil
}

func (c *Client) Status(ctx context.Context, id string) (Operation, error) {
	id = canonicalIdentifier(id)
	if !identifier.MatchString(id) {
		return Operation{}, output.New(2, "Invalid Package operation ID")
	}
	result, err := c.operation(ctx, http.MethodGet, "/operations/"+id, nil)
	if err == nil && result.OperationID != id {
		return Operation{}, output.New(9, "Server returned a different Package operation")
	}
	return result, err
}

func (c *Client) Lookup(ctx context.Context, key string) (Operation, error) {
	if !identifier.MatchString(key) {
		return Operation{}, output.New(2, "Invalid Package idempotency key")
	}
	return c.operation(ctx, http.MethodPost, "/operations/lookup", map[string]any{"idempotency_key": key})
}

func (c *Client) Cancel(ctx context.Context, id string) (Operation, error) {
	id = canonicalIdentifier(id)
	if !identifier.MatchString(id) {
		return Operation{}, output.New(2, "Invalid Package operation ID")
	}
	result, err := c.operation(ctx, http.MethodPost, "/operations/"+id+"/cancel", map[string]any{})
	if err == nil && result.OperationID != id {
		return Operation{}, output.New(9, "Server returned a different Package operation")
	}
	return result, err
}

func (c *Client) Resume(ctx context.Context, id string, revision int64) (Operation, error) {
	id = canonicalIdentifier(id)
	if !identifier.MatchString(id) || revision < 1 {
		return Operation{}, output.New(2, "Resume requires an observed operation revision")
	}
	result, err := c.operation(ctx, http.MethodPost, "/operations/"+id+"/resume", map[string]any{"expected_revision": revision})
	if err == nil && result.OperationID != id {
		return Operation{}, output.New(9, "Server returned a different Package operation")
	}
	return result, err
}

type RegistryBinding struct {
	FrozenEvidenceRetained bool              `json:"frozen_evidence_retained"`
	SourceKind             string            `json:"source_kind"`
	AcceptedRevision       any               `json:"accepted_revision"`
	CurrentRevision        any               `json:"current_revision"`
	GenerationScope        string            `json:"generation_scope"`
	BindingStatus          string            `json:"binding_status"`
	Frozen                 bool              `json:"frozen"`
	SnapshotID             string            `json:"snapshot_id"`
	Identifiers            map[string]string `json:"identifiers,omitempty"`
	ResourceUID            string            `json:"resource_uid"`
	Kind                   string            `json:"kind"`
	ResourceID             string            `json:"resource_id"`
	Revision               any               `json:"revision"`
	DefinitionDigest       string            `json:"definition_digest"`
	OperationID            string            `json:"operation_id"`
}
type Registry struct {
	RegistryID string            `json:"registry_id"`
	Resources  []RegistryBinding `json:"resources"`
}

func (c *Client) Registry(ctx context.Context, id string) (Registry, error) {
	id = canonicalIdentifier(id)
	var result Registry
	if !identifier.MatchString(id) {
		return result, output.New(2, "Invalid registry identity")
	}
	err := c.request(ctx, http.MethodGet, "/registries/"+id, nil, &result)
	if err == nil && result.RegistryID != id {
		return result, output.New(9, "Registry identity differs from the requested scope")
	}
	return result, err
}
