package packageapi

import (
	"context"
	"encoding/json"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"reflect"
	"regexp"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

var digestPattern = regexp.MustCompile(`^[a-f0-9]{64}$`)

func validExpiry(value string) bool {
	expires, err := time.Parse(time.RFC3339Nano, value)
	return err == nil && expires.After(time.Now())
}

type Upload struct {
	PackageSchemaVersion string                        `json:"package_schema_version"`
	UploadID             string                        `json:"upload_id"`
	ProjectID            string                        `json:"project_id"`
	ArtifactDigest       string                        `json:"artifact_digest"`
	Inventory            []packagebundle.InventoryFile `json:"inventory"`
	ExpiresAt            string                        `json:"expires_at"`
}

func (c *Client) Upload(ctx context.Context, bundle *packagebundle.Bundle, locked bool) (Upload, error) {
	version := packagefmt.Text(bundle.Graph.Manifest["schema_version"])
	if err := c.RequireSchema(ctx, version, version == "2.0"); err != nil {
		return Upload{}, err
	}
	reader, writer := io.Pipe()
	defer reader.Close()
	form := multipart.NewWriter(writer)
	completed := make(chan error, 1)
	go func() {
		part, err := form.CreateFormFile("file", "package.tar.gz")
		if err == nil {
			err = bundle.Archive(part, true)
		}
		if err == nil {
			err = form.Close()
		}
		_ = writer.CloseWithError(err)
		completed <- err
	}()
	query := url.Values{}
	if locked {
		query.Set("locked", "true")
	}
	value, _, err := c.Control.RequestReader(ctx, http.MethodPost, c.path("/uploads"), query, reader, form.FormDataContentType())
	_ = reader.Close()
	captureErr := <-completed
	if err != nil {
		return Upload{}, err
	}
	if captureErr != nil {
		return Upload{}, output.New(2, "Captured package changed during upload")
	}
	envelope, ok := value.(map[string]any)
	if !ok || envelope["success"] != true {
		return Upload{}, output.New(9, "Invalid Package upload envelope")
	}
	encoded, _ := json.Marshal(envelope["data"])
	var result Upload
	if json.Unmarshal(encoded, &result) != nil || result.PackageSchemaVersion != version || result.ProjectID != c.ProjectID ||
		!identifier.MatchString(result.UploadID) || result.ArtifactDigest != bundle.ArtifactDigest || !reflect.DeepEqual(result.Inventory, bundle.Inventory) || !validExpiry(result.ExpiresAt) {
		return Upload{}, output.New(9, "Server accepted a different Package artifact")
	}
	return result, nil
}

type PlanRequest struct {
	InstallationMode string                       `json:"installation_mode,omitempty"`
	RegistryID       string                       `json:"registry_id,omitempty"`
	ResourceBindings map[string]DevelopmentTarget `json:"resource_bindings,omitempty"`
	Mode             string                       `json:"mode"`
	UploadID         string                       `json:"upload_id"`
	ArtifactDigest   string                       `json:"artifact_digest"`
	Bindings         map[string]any               `json:"bindings"`
	Lifecycle        string                       `json:"lifecycle"`
	ReleaseNotes     *string                      `json:"release_notes"`
	Reason           *string                      `json:"reason"`
}
type Effect struct {
	Key                 string   `json:"key"`
	Owner               string   `json:"owner"`
	Action              string   `json:"action"`
	Component           string   `json:"component,omitempty"`
	Permission          string   `json:"permission"`
	RequiredPermissions []string `json:"required_permissions,omitempty"`
	State               string   `json:"state"`
}
type Plan struct {
	ConstituentBindingPolicy string                       `json:"constituent_binding_policy,omitempty"`
	InstallationMode         string                       `json:"installation_mode,omitempty"`
	Mode                     string                       `json:"mode,omitempty"`
	RegistryID               string                       `json:"registry_id,omitempty"`
	ResourceBindings         map[string]DevelopmentTarget `json:"resource_bindings,omitempty"`
	APIOrigin                string                       `json:"api_origin"`
	PackageSchemaVersion     string                       `json:"package_schema_version"`
	PlanID                   string                       `json:"plan_id"`
	PlanDigest               string                       `json:"plan_digest"`
	ProjectID                string                       `json:"project_id"`
	UploadID                 string                       `json:"upload_id"`
	ArtifactDigest           string                       `json:"artifact_digest"`
	DefinitionDigest         string                       `json:"definition_digest"`
	CapabilitiesDigest       string                       `json:"capabilities_digest"`
	BindingsDigest           string                       `json:"bindings_digest"`
	Bindings                 map[string]any               `json:"bindings"`
	Lifecycle                string                       `json:"lifecycle"`
	ReleaseNotes             *string                      `json:"release_notes"`
	Reason                   *string                      `json:"reason"`
	Effects                  []Effect                     `json:"effects"`
	RequiredPermissions      []string                     `json:"required_permissions"`
	CreatedAt                string                       `json:"created_at"`
	ExpiresAt                string                       `json:"expires_at"`
}

func (c *Client) Plan(ctx context.Context, request PlanRequest) (Plan, error) {
	var result Plan
	version := packagefmt.Text(request.Bindings["schema_version"])
	if version == "2.0" && request.InstallationMode != "structural" {
		return result, output.New(2, "Package 2.0 requires --structural")
	}
	if err := c.RequireSchema(ctx, version, request.InstallationMode == "structural"); err != nil {
		return result, err
	}
	err := c.request(ctx, http.MethodPost, "/plan", request, &result)
	if err != nil {
		return result, err
	}
	if result.PackageSchemaVersion != version || result.InstallationMode != request.InstallationMode {
		return Plan{}, output.New(9, "Server changed Package schema or installation mode")
	}
	if request.Mode == "sync" {
		if result.Mode != "sync" || result.RegistryID != request.RegistryID || len(result.ResourceBindings) != len(request.ResourceBindings) {
			return Plan{}, output.New(9, "Server changed the development registry identity")
		}
		for key, expected := range request.ResourceBindings {
			observed, exists := result.ResourceBindings[key]
			observed.DefinitionDigest = ""
			left, _ := json.Marshal(expected)
			right, _ := json.Marshal(observed)
			if !exists || string(left) != string(right) {
				return Plan{}, output.New(9, "Server changed an approved native resource binding")
			}
		}
	}
	bindingsDigest, bindingsErr := BindingsDigest(result.Bindings)
	if bindingsErr != nil || bindingsDigest != result.BindingsDigest {
		return Plan{}, output.New(9, "Server Package binding digest does not match approved identities")
	}
	if !identifier.MatchString(result.PlanID) || result.ProjectID != c.ProjectID || result.UploadID != request.UploadID ||
		result.ArtifactDigest != request.ArtifactDigest || result.Lifecycle != request.Lifecycle || !digestPattern.MatchString(result.PlanDigest) || !digestPattern.MatchString(result.DefinitionDigest) ||
		!digestPattern.MatchString(result.CapabilitiesDigest) || !digestPattern.MatchString(result.BindingsDigest) ||
		result.APIOrigin != c.Control.Base || !reflect.DeepEqual(result.Bindings, request.Bindings) ||
		!reflect.DeepEqual(result.ReleaseNotes, request.ReleaseNotes) || !reflect.DeepEqual(result.Reason, request.Reason) ||
		!validExpiry(result.ExpiresAt) || len(result.Effects) == 0 {
		return Plan{}, output.New(9, "Server returned a different Package plan identity")
	}
	return result, nil
}

type DevelopmentTarget struct {
	DefinitionDigest string `json:"definition_digest,omitempty"`
	SourceExportID   string `json:"source_export_id,omitempty"`
	SourceComponent  string `json:"source_component,omitempty"`
	ResourceUID      string `json:"resource_uid"`
	ResourceID       string `json:"resource_id,omitempty"`
	ExpectedRevision any    `json:"expected_revision"`
	SnapshotID       string `json:"release_id,omitempty"`
}
