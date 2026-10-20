package packageapi

import (
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"net/http"
)

type ApplyRequest struct {
	InstallationMode  string            `json:"installation_mode,omitempty"`
	PlanID            string            `json:"plan_id"`
	PlanDigest        string            `json:"plan_digest"`
	UploadID          string            `json:"upload_id"`
	ArtifactDigest    string            `json:"artifact_digest"`
	Bindings          map[string]any    `json:"bindings"`
	ProtectedBindings map[string]string `json:"protected_bindings"`
	Lifecycle         string            `json:"lifecycle"`
	ReleaseNotes      *string           `json:"release_notes"`
	Reason            *string           `json:"reason"`
}

// Apply performs one POST only. Recovery uses Lookup with the same request key;
// neither this client nor the underlying control transport retries mutations.
func (c *Client) Apply(ctx context.Context, key string, request ApplyRequest) (Operation, error) {
	if !identifier.MatchString(key) || !identifier.MatchString(request.PlanID) || !identifier.MatchString(request.UploadID) || !digestPattern.MatchString(request.PlanDigest) || !digestPattern.MatchString(request.ArtifactDigest) {
		return Operation{}, output.New(2, "Invalid Package apply identity")
	}
	version := packagefmt.Text(request.Bindings["schema_version"])
	if version == "" {
		version = "1.0"
	}
	structural := request.InstallationMode == "structural"
	if (request.InstallationMode != "" && request.InstallationMode != "operational" && !structural) || (version == "2.0" && !structural) || (structural && (request.Lifecycle != "draft" || len(request.ProtectedBindings) > 0)) {
		return Operation{}, output.New(2, "Structural installation requires Draft and remote configuration references only")
	}
	if err := c.RequireSchema(ctx, version, structural); err != nil {
		return Operation{}, err
	}
	encoded, encodingErr := json.Marshal(request)
	if encodingErr != nil || len(encoded) > 2<<20 {
		return Operation{}, output.New(2, "Invalid or oversized Package apply request")
	}
	control := *c.Control
	control.Headers = c.Control.Headers.Clone()
	control.Headers.Del("If-Match")
	control.Headers.Set("Idempotency-Key", key)
	scoped := *c
	scoped.Control = &control
	result, err := scoped.operation(ctx, http.MethodPost, "/apply", request)
	if err != nil {
		normalized := output.Normalize(err)
		if normalized.Outcome == "" {
			normalized.Outcome = "unknown"
		}
		return result, normalized
	}
	if err == nil && (result.ArtifactDigest != request.ArtifactDigest || result.PackageSchemaVersion != version) {
		return Operation{}, &output.Error{Code: 9, Message: "Server returned a different accepted Package artifact", Outcome: "unknown"}
	}
	return result, err
}
