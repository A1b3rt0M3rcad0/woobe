package packageapi

import (
	"bytes"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"net/url"
	"time"
)

type PlanReceipt struct {
	Format               string `json:"format"`
	SchemaVersion        string `json:"schema_version"`
	PrincipalFingerprint string `json:"principal_fingerprint"`
	Plan                 Plan   `json:"plan"`
}

func (r PlanReceipt) Validate() error {
	if r.Format != "woobe-package-plan-receipt" || r.SchemaVersion != "1.0" || !digestPattern.MatchString(r.PrincipalFingerprint) || !validExpiry(r.Plan.ExpiresAt) || !digestPattern.MatchString(r.Plan.PlanDigest) || !identifier.MatchString(r.Plan.PlanID) {
		return output.New(2, "Invalid or expired Package plan receipt")
	}
	origin, err := url.Parse(r.Plan.APIOrigin)
	if err != nil || origin.Host == "" || origin.User != nil || origin.RawQuery != "" || origin.Fragment != "" || origin.Path != "" && origin.Path != "/" || origin.Scheme != "http" && origin.Scheme != "https" {
		return output.New(2, "Invalid Package plan origin")
	}
	for _, id := range []string{r.Plan.ProjectID, r.Plan.UploadID} {
		if !identifier.MatchString(id) {
			return output.New(2, "Invalid Package plan identity")
		}
	}
	for _, value := range []string{r.Plan.ArtifactDigest, r.Plan.DefinitionDigest, r.Plan.CapabilitiesDigest, r.Plan.BindingsDigest} {
		if !digestPattern.MatchString(value) {
			return output.New(2, "Invalid Package plan digest")
		}
	}
	created, e := time.Parse(time.RFC3339Nano, r.Plan.CreatedAt)
	expires, e2 := time.Parse(time.RFC3339Nano, r.Plan.ExpiresAt)
	if e != nil || e2 != nil || !expires.After(created) || len(r.Plan.Effects) == 0 || (r.Plan.PackageSchemaVersion != "1.0" && r.Plan.PackageSchemaVersion != "2.0") {
		return output.New(2, "Invalid Package plan metadata")
	}
	if r.Plan.Bindings["schema_version"] != r.Plan.PackageSchemaVersion || (r.Plan.InstallationMode != "" && r.Plan.InstallationMode != "structural") || (r.Plan.InstallationMode == "structural" && r.Plan.Lifecycle != "draft") || (r.Plan.PackageSchemaVersion == "2.0" && r.Plan.InstallationMode != "structural") {
		return output.New(2, "Invalid Package installation mode or schema identity")
	}
	if r.Plan.Lifecycle != "draft" && r.Plan.Lifecycle != "staging" && r.Plan.Lifecycle != "release" && r.Plan.Lifecycle != "production" {
		return output.New(2, "Invalid Package plan lifecycle")
	}
	if packagefmt.Validate(&packagefmt.Document{Value: r.Plan.Bindings, File: "approved-bindings"}) != nil {
		return output.New(2, "Invalid approved Package bindings")
	}
	digest, err := BindingsDigest(r.Plan.Bindings)
	if err != nil || digest != r.Plan.BindingsDigest {
		return output.New(2, "Approved Package binding identities changed")
	}
	return nil
}
func (r PlanReceipt) Save(path string) error {
	if err := r.Validate(); err != nil {
		return err
	}
	data, err := json.Marshal(r)
	if err != nil {
		return err
	}
	return packagecheckpoint.WritePrivateExclusive(path, data)
}
func LoadPlanReceipt(path string) (PlanReceipt, error) {
	var result PlanReceipt
	data, err := packagecheckpoint.ReadPrivate(path)
	if err != nil {
		return result, err
	}
	if jsoninput.Validate(data) != nil {
		return result, output.New(2, "Invalid Package plan receipt JSON")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&result) != nil {
		return result, output.New(2, "Invalid Package plan receipt fields")
	}
	return result, result.Validate()
}
