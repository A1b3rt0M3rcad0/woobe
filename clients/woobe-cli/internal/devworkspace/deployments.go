package devworkspace

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

// These portable receipts prove content integrity, not offline server authority.
func ValidateDeploymentReceipt(record map[string]any, plan bool) error {
	invalid := func() error {
		return fmt.Errorf("ASAC_DEPLOYMENT_RECEIPT_INVALID: exact identity or integrity mismatch")
	}
	key, scope, state := "receipt_digest", "deployment-receipt", "committed"
	fields := []string{"deployment_id", "plan_id", "outbox_id"}
	if plan {
		key, scope, state = "plan_digest", "deployment-plan", "planned"
		fields = []string{"plan_id"}
	}
	value := clone(record)
	expected := packagefmt.Text(value[key])
	delete(value, key)
	digest, err := asac.Digest(scope, value)
	if err != nil || digest != expected || record["schema_version"] != "1.0" || record["state"] != state || record["complete"] != true || record["write_outcome"] != "committed" || record["clock_authority"] != "database" {
		return invalid()
	}
	fields = append(fields, "project_id", "resource_id", "publication_id", "release_id", "operation_id", "candidate_id", "evaluation_id")
	for _, field := range fields {
		if !uuidPattern.MatchString(packagefmt.Text(record[field])) {
			return invalid()
		}
	}
	if record["kind"] != "Agent" && record["kind"] != "Network" {
		return invalid()
	}
	if record["environment"] != "staging" && record["environment"] != "production" {
		return invalid()
	}
	if record["action"] != "activate" && record["action"] != "rollback" {
		return invalid()
	}
	if len(strings.TrimSpace(packagefmt.Text(record["reason"]))) < 3 || packagefmt.Text(record["actor"]) == "" {
		return invalid()
	}
	for _, field := range []string{"runtime_digest", "record_digest", "binding_digest", "project_policy_digest"} {
		if !historyDigest.MatchString(packagefmt.Text(record[field])) {
			return invalid()
		}
	}
	if _, err = time.Parse(time.RFC3339Nano, packagefmt.Text(record["created_at"])); err != nil {
		return invalid()
	}
	integer := func(key string) (int64, bool) {
		raw, err := json.Marshal(record[key])
		if err != nil {
			return 0, false
		}
		n, err := strconv.ParseInt(string(raw), 10, 64)
		return n, err == nil && n >= 0
	}
	if plan {
		if _, ok := integer("expected_generation"); !ok {
			return invalid()
		}
	} else {
		before, ok := integer("generation_before")
		if !ok {
			return invalid()
		}
		after, ok := integer("generation_after")
		if !ok || after < before || after-before > 1 {
			return invalid()
		}
		changed, ok := record["selection_changed"].(bool)
		if !ok || changed != (after > before) {
			return invalid()
		}
		proofs := packagefmt.List(record["leases"])
		if len(proofs) != 1 {
			return invalid()
		}
		proof := packagefmt.Object(proofs[0])
		for _, key := range []string{"lease_id", "workflow_id"} {
			if !uuidPattern.MatchString(packagefmt.Text(proof[key])) {
				return invalid()
			}
		}
		raw, _ := json.Marshal(proof["fencing_token"])
		n, err := strconv.ParseInt(string(raw), 10, 64)
		if err != nil || n <= 0 {
			return invalid()
		}
	}
	if plan {
		if record["executed"] != false {
			return invalid()
		}
		if _, err = time.Parse(time.RFC3339Nano, packagefmt.Text(record["expires_at"])); err != nil {
			return invalid()
		}
	}
	return nil
}

func (c *Config) StoreDeploymentReceipt(resource Resource, target, workspace, project string, record map[string]any, plan bool) error {
	if err := ValidateDeploymentReceipt(record, plan); err != nil {
		return err
	}
	if record["project_id"] != project || record["kind"] != resource.Kind {
		return fmt.Errorf("Deployment destination mismatch")
	}
	namespace, err := asac.Digest("destination", []string{target, workspace, project})
	if err != nil {
		return err
	}
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return err
	}
	category, key := "deployment-receipts", "deployment_id"
	if plan {
		category, key = "deployment-plans", "plan_id"
	}
	wrapper := map[string]any{"format": "woobe-observed-" + category, "schema_version": "1.0", "resource_uid": resource.UID, "target": target, "workspace_id": workspace, "project_id": project, "receipt": record, "authenticity": "authenticated_connection_observation"}
	data, err := Encode(wrapper)
	if err != nil {
		return err
	}
	return c.immutableWrite(filepath.Join(dir, category, strings.TrimPrefix(namespace, "sha256:")+"_"+packagefmt.Text(record[key])+".yaml"), data)
}

func (c *Config) VerifyDeploymentReceipts(resource Resource, plan bool) (int, error) {
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return 0, err
	}
	category, key := "deployment-receipts", "deployment_id"
	if plan {
		category, key = "deployment-plans", "plan_id"
	}
	base := filepath.Join(dir, category)
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
		return 0, fmt.Errorf("ASaC deployment receipts exceed local record limit")
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
		if wrapper.Format != "woobe-observed-"+category || wrapper.Version != "1.0" || wrapper.UID != resource.UID || wrapper.Authenticity != "authenticated_connection_observation" || wrapper.Receipt["project_id"] != wrapper.Project || wrapper.Receipt["kind"] != resource.Kind {
			return 0, fmt.Errorf("ASAC_DEPLOYMENT_RECEIPT_INVALID: destination scope mismatch")
		}
		if err = ValidateDeploymentReceipt(wrapper.Receipt, plan); err != nil {
			return 0, err
		}
		namespace, err := asac.Digest("destination", []string{wrapper.Target, wrapper.Workspace, wrapper.Project})
		if err != nil {
			return 0, err
		}
		if file.Name() != strings.TrimPrefix(namespace, "sha256:")+"_"+packagefmt.Text(wrapper.Receipt[key])+".yaml" {
			return 0, fmt.Errorf("ASAC_DEPLOYMENT_RECEIPT_INVALID: filename identity mismatch")
		}
		count++
	}
	return count, nil
}
