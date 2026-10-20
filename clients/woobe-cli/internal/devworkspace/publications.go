package devworkspace

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

// An authenticated observation and a content digest do not establish offline
// server authenticity. Signing/trust verification is a separate protocol.
func ValidatePublicationReceipt(record map[string]any) error {
	value := clone(record)
	expected := packagefmt.Text(value["receipt_digest"])
	delete(value, "receipt_digest")
	digest, err := asac.Digest("publication-receipt", value)
	if err != nil || digest != expected || record["schema_version"] != "1.0" || record["state"] != "published" || record["published"] != true || record["production_changed"] != false || record["write_outcome"] != "committed" {
		return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: integrity or outcome mismatch")
	}
	for _, field := range []string{"publication_id", "operation_id", "resource_uid", "resource_id", "project_id", "candidate_id", "evaluation_id", "release_id"} {
		if !uuidPattern.MatchString(packagefmt.Text(record[field])) {
			return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: %s", field)
		}
	}
	if !revisionID.MatchString(packagefmt.Text(record["revision_id"])) {
		return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: revision identity")
	}
	for _, field := range []string{"record_digest", "definition_digest", "artifact_digest", "runtime_digest", "binding_digest", "suite_digest", "dataset_digest", "policy_digest"} {
		if !historyDigest.MatchString(packagefmt.Text(record[field])) {
			return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: %s", field)
		}
	}
	if record["kind"] != "Agent" && record["kind"] != "Network" {
		return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: resource kind")
	}
	actor := packagefmt.Text(record["actor"])
	parts := strings.SplitN(actor, ":", 2)
	if len(parts) != 2 || (parts[0] != "user" && parts[0] != "control") || !uuidPattern.MatchString(parts[1]) {
		return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: actor identity")
	}
	if _, err := time.Parse(time.RFC3339Nano, packagefmt.Text(record["created_at"])); err != nil {
		return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: timestamp")
	}
	if _, ok := record["reused"].(bool); !ok || record["complete"] != true {
		return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: terminal outcome")
	}
	git := packagefmt.Object(record["git"])
	if git["status"] != "unavailable" && git["status"] != "declared" {
		return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: unsupported Git attestation")
	}
	allowed := map[string]bool{}
	for _, key := range []string{"schema_version", "kind", "publication_id", "project_id", "resource_id", "resource_uid", "operation_id", "write_outcome", "state", "candidate_id", "evaluation_id", "release_id", "release_version", "reused", "revision_id", "actor", "reason", "created_at", "record_digest", "runtime_digest", "definition_digest", "artifact_digest", "binding_digest", "suite_digest", "dataset_digest", "policy_digest", "git", "published", "production_changed", "complete", "receipt_digest", "runtime_digest_scope", "constituent_releases"} {
		allowed[key] = true
	}
	for key := range record {
		if !allowed[key] {
			return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: unexpected field")
		}
	}
	if record["kind"] == "Network" {
		if record["runtime_digest_scope"] != "network-execution-runtime@2" {
			return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: Network runtime scope")
		}
		children, ok := record["constituent_releases"].([]any)
		if !ok || len(children) == 0 || len(children) > 1024 {
			return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: constituent evidence")
		}
		seen := map[string]bool{}
		for _, raw := range children {
			child, ok := raw.(map[string]any)
			if !ok || len(child) != 5 {
				return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: constituent shape")
			}
			for _, key := range []string{"node_id", "agent_id", "source_snapshot_id", "release_id"} {
				if !uuidPattern.MatchString(packagefmt.Text(child[key])) {
					return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: constituent %s", key)
				}
			}
			node := packagefmt.Text(child["node_id"])
			if seen[node] || !historyDigest.MatchString(packagefmt.Text(child["runtime_digest"])) {
				return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: constituent identity/digest")
			}
			seen[node] = true
		}
	} else if record["runtime_digest_scope"] != nil || record["constituent_releases"] != nil {
		return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: Agent contains Network evidence")
	}
	return nil
}

func ValidatePublicationPreparation(record map[string]any) error {
	invalid := func() error {
		return fmt.Errorf("ASAC_PUBLICATION_PREPARATION_INVALID: identity, scope or outcome mismatch")
	}
	if record["schema_version"] != "1.0" || record["kind"] != "Network" || record["accepted"] != true || record["published"] != false || record["production_changed"] != false || record["write_outcome"] != "committed" || record["runtime_digest_scope"] != "network-execution-runtime@2" {
		return invalid()
	}
	cancelled := record["state"] == "cancelled"
	if (!cancelled && record["state"] != "preparing") || record["complete"] != cancelled {
		return invalid()
	}
	for _, key := range []string{"publication_id", "operation_id", "resource_uid", "resource_id", "project_id", "candidate_id", "evaluation_id"} {
		if !uuidPattern.MatchString(packagefmt.Text(record[key])) {
			return invalid()
		}
	}
	for _, key := range []string{"record_digest", "runtime_digest"} {
		if !historyDigest.MatchString(packagefmt.Text(record[key])) {
			return invalid()
		}
	}
	count := func(value any) (int, bool) {
		var f float64
		switch v := value.(type) {
		case int:
			f = float64(v)
		case float64:
			f = v
		case json.Number:
			var err error
			f, err = v.Float64()
			if err != nil {
				return 0, false
			}
		default:
			return 0, false
		}
		return int(f), f >= 0 && f <= 1024 && math.Trunc(f) == f
	}
	prepared, p := count(record["prepared_constituents"])
	required, r := count(record["required_constituents"])
	if !p || !r || required == 0 || prepared > required {
		return invalid()
	}
	allowed := map[string]bool{}
	for _, key := range []string{"schema_version", "kind", "publication_id", "project_id", "resource_id", "resource_uid", "operation_id", "candidate_id", "evaluation_id", "state", "accepted", "published", "production_changed", "complete", "write_outcome", "prepared_constituents", "required_constituents", "error_code", "runtime_digest", "runtime_digest_scope", "record_digest"} {
		allowed[key] = true
	}
	if cancelled {
		value := clone(record)
		delete(value, "receipt_digest")
		digest, err := asac.Digest("publication-cancellation", value)
		parts := strings.SplitN(packagefmt.Text(record["actor"]), ":", 2)
		if err != nil || digest != record["receipt_digest"] || len(parts) != 2 || (parts[0] != "user" && parts[0] != "control") || !uuidPattern.MatchString(parts[1]) || len(strings.TrimSpace(packagefmt.Text(record["reason"]))) < 3 {
			return invalid()
		}
		allowed["actor"] = true
		allowed["reason"] = true
		allowed["receipt_digest"] = true
	}
	for key := range record {
		if !allowed[key] {
			return invalid()
		}
	}
	return nil
}

func (c *Config) StorePublicationReceipt(resource Resource, target, workspace, project string, record map[string]any) error {
	return c.storePublicationObservation(resource, target, workspace, project, record, false)
}
func (c *Config) StorePublicationCancellation(resource Resource, target, workspace, project string, record map[string]any) error {
	return c.storePublicationObservation(resource, target, workspace, project, record, true)
}
func (c *Config) storePublicationObservation(resource Resource, target, workspace, project string, record map[string]any, cancellation bool) error {
	validate := ValidatePublicationReceipt
	directory, format := "publications", "woobe-observed-publication"
	if cancellation {
		validate = ValidatePublicationPreparation
		directory = "cancellations"
		format = "woobe-observed-publication-cancellation"
		if record["state"] != "cancelled" {
			return fmt.Errorf("Cancellation is not terminal")
		}
	}
	if err := validate(record); err != nil {
		return err
	}
	if record["resource_uid"] != resource.UID || record["project_id"] != project || record["kind"] != resource.Kind {
		return fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: destination identity mismatch")
	}
	namespace, err := asac.Digest("destination", []string{target, workspace, project})
	if err != nil {
		return err
	}
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return err
	}
	wrapper := map[string]any{"format": format, "schema_version": "1.0", "resource_uid": resource.UID, "target": target, "workspace_id": workspace, "project_id": project, "receipt": record, "authenticity": "authenticated_connection_observation"}
	data, err := Encode(wrapper)
	if err != nil {
		return err
	}
	return c.immutableWrite(filepath.Join(dir, directory, strings.TrimPrefix(namespace, "sha256:")+"_"+packagefmt.Text(record["publication_id"])+".yaml"), data)
}

func (c *Config) VerifyPublicationReceipts(resource Resource) (int, error) {
	return c.verifyPublicationObservations(resource, false)
}
func (c *Config) VerifyPublicationCancellations(resource Resource) (int, error) {
	return c.verifyPublicationObservations(resource, true)
}
func (c *Config) verifyPublicationObservations(resource Resource, cancellation bool) (int, error) {
	validate := ValidatePublicationReceipt
	directory, format := "publications", "woobe-observed-publication"
	if cancellation {
		validate = ValidatePublicationPreparation
		directory = "cancellations"
		format = "woobe-observed-publication-cancellation"
	}
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return 0, err
	}
	base := filepath.Join(dir, directory)
	if err = confinedParents(c.RootPath(), filepath.Join(base, "receipt.yaml")); err != nil {
		return 0, err
	}
	files, err := os.ReadDir(base)
	if os.IsNotExist(err) {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}
	if len(files) > 10000 {
		return 0, fmt.Errorf("ASaC publication receipts exceed local record limit")
	}
	count := 0
	for _, file := range files {
		if strings.HasPrefix(file.Name(), ".asac-") {
			continue
		}
		var wrapper struct {
			Format       string         `json:"format"`
			Version      string         `json:"schema_version"`
			UID          string         `json:"resource_uid"`
			Target       string         `json:"target"`
			Workspace    string         `json:"workspace_id"`
			Project      string         `json:"project_id"`
			Receipt      map[string]any `json:"receipt"`
			Authenticity string         `json:"authenticity"`
		}
		if err = readHistoryJSON(c, filepath.Join(base, file.Name()), &wrapper); err != nil {
			return 0, err
		}
		if wrapper.Format != format || wrapper.Version != "1.0" || wrapper.UID != resource.UID || wrapper.Authenticity != "authenticated_connection_observation" || wrapper.Receipt["project_id"] != wrapper.Project || wrapper.Receipt["resource_uid"] != resource.UID || wrapper.Receipt["kind"] != resource.Kind {
			return 0, fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: scope mismatch")
		}
		if cancellation && wrapper.Receipt["state"] != "cancelled" {
			return 0, fmt.Errorf("Invalid cancellation outcome")
		}
		if err = validate(wrapper.Receipt); err != nil {
			return 0, err
		}
		namespace, digestErr := asac.Digest("destination", []string{wrapper.Target, wrapper.Workspace, wrapper.Project})
		if digestErr != nil {
			return 0, digestErr
		}
		if file.Name() != strings.TrimPrefix(namespace, "sha256:")+"_"+packagefmt.Text(wrapper.Receipt["publication_id"])+".yaml" {
			return 0, fmt.Errorf("ASAC_PUBLICATION_RECEIPT_INVALID: filename identity mismatch")
		}
		count++
	}
	return count, nil
}
