package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

func deploymentTestPlan(body map[string]any, project, id string) map[string]any {
	uuid := "12345678-1234-4321-8321-123456789019"
	data := map[string]any{"schema_version": "1.0", "kind": "Agent", "project_id": project, "resource_id": id,
		"operation_id": body["operation_id"], "environment": body["environment"], "release_id": body["release_id"],
		"publication_id": uuid, "candidate_id": uuid, "evaluation_id": uuid, "plan_id": uuid,
		"expected_generation": body["expected_generation"], "reason": body["reason"], "action": body["action"],
		"state": "planned", "executed": false, "complete": true, "write_outcome": "committed", "clock_authority": "database",
		"actor": "control:test", "created_at": time.Now().UTC().Format(time.RFC3339Nano), "expires_at": time.Now().Add(time.Minute).UTC().Format(time.RFC3339Nano)}
	for _, key := range []string{"runtime_digest", "record_digest", "binding_digest", "project_policy_digest"} {
		data[key] = "sha256:" + strings.Repeat("a", 64)
	}
	digest, _ := asac.Digest("deployment-plan", data)
	data["plan_digest"] = digest
	return data
}

func TestDeploymentNativePlanAndReadOnlyOriginalRecoveryWithoutProjectConfig(t *testing.T) {
	const native = "01a0a033-5820-770c-854b-902864857273"
	const project = "12345678-1234-4321-8321-123456789099"
	const operation = "12345678-1234-4321-8321-123456789017"
	var receipt map[string]any
	writes := 0
	lost := true
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var data any
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"asac": map[string]any{"schema_version": "1.0", "fenced_deployment": true, "deployment_scope": "exact-release-owner-selection@1"}}
		case strings.HasSuffix(r.URL.Path, "/deployment-plans"):
			writes++
			var body map[string]any
			decoder := json.NewDecoder(r.Body)
			decoder.UseNumber()
			_ = decoder.Decode(&body)
			receipt = deploymentTestPlan(body, project, native)
			if lost {
				w.WriteHeader(500)
				_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "lost acceptance"})
				return
			}
			data = receipt
		case strings.Contains(r.URL.Path, "/operations/"):
			data = map[string]any{"operation_id": operation, "state": "committed", "result": receipt}
		default:
			t.Error("unexpected request", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", project, "--no-project-config", "--output", "json"}
	plan := append([]string{"agent", native, "deployment", "plan", "--operation", operation, "--release", native, "--expected-generation", "4", "--notes", "Activate qualified revision"}, flags...)
	if code, value := invoke(t, plan, ""); code == 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	recovered := append([]string{"agent", native, "deployment", "reconcile", "--operation", operation}, flags...)
	if code, value := invoke(t, recovered, ""); code != 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	if err := devworkspace.ValidateDeploymentReceipt(receipt, true); err != nil {
		t.Fatal(err)
	}
	receipt["release_id"] = "invalid"
	if err := devworkspace.ValidateDeploymentReceipt(receipt, true); err == nil {
		t.Fatal("tampered plan accepted")
	}
}

func TestDeploymentRejectsIncompleteAuthorityBeforeNetworkIO(t *testing.T) {
	for _, args := range [][]string{
		{"agent", "01a0a033-5820-770c-854b-902864857273", "deployment", "plan", "--release", "01a0a033-5820-770c-854b-902864857273", "--notes", "Valid reason"},
		{"network", "01a0a033-5820-770c-854b-902864857273", "deployment", "apply", "01a0a033-5820-770c-854b-902864857273"},
		{"agent", "01a0a033-5820-770c-854b-902864857273", "deployment", "plan", "--env", "draft"},
	} {
		if code, value := invoke(t, args, ""); code != 2 {
			t.Fatal(code, value)
		}
	}
}

func TestRegisteredDeploymentLostResponseMirrorsOriginalPlanBeforeClearing(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	const project = "12345678-1234-4321-8321-123456789099"
	const native = "01a0a033-5820-770c-854b-902864857273"
	var receipt map[string]any
	writes := 0
	mismatch := true
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var data any
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"asac": map[string]any{"schema_version": "1.0", "fenced_deployment": true, "deployment_scope": "exact-release-owner-selection@1"}}
		case strings.HasSuffix(r.URL.Path, "/deployment-plans"):
			writes++
			var body map[string]any
			decoder := json.NewDecoder(r.Body)
			decoder.UseNumber()
			_ = decoder.Decode(&body)
			receipt = deploymentTestPlan(body, project, native)
			w.WriteHeader(500)
			_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "lost acceptance"})
			return
		case strings.Contains(r.URL.Path, "/operations/"):
			value := map[string]any{}
			for key, item := range receipt {
				value[key] = item
			}
			if mismatch {
				value["release_id"] = "12345678-1234-4321-8321-123456789077"
				delete(value, "plan_digest")
				digest, _ := asac.Digest("deployment-plan", value)
				value["plan_digest"] = digest
			}
			data = map[string]any{"operation_id": receipt["operation_id"], "state": "committed", "result": value}
		default:
			t.Error("unexpected request", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	c, state, resource := asacWorkspace(t, server.URL)
	state.Project = project
	tracking, err := c.ReadTracking(resource)
	if err != nil {
		t.Fatal(err)
	}
	tracking.Origin.Project = project
	trackingPath, err := c.TrackingPath(resource)
	if err != nil {
		t.Fatal(err)
	}
	trackingJSON, err := json.Marshal(tracking)
	if err != nil {
		t.Fatal(err)
	}
	var trackingObject map[string]any
	if err = json.Unmarshal(trackingJSON, &trackingObject); err != nil {
		t.Fatal(err)
	}
	trackingBytes, err := devworkspace.Encode(trackingObject)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(trackingPath, trackingBytes, 0600); err != nil {
		t.Fatal(err)
	}
	rootBinding := state.Bindings[resource.UID]
	rootBinding.ResourceID = ""
	state.Bindings[resource.UID] = rootBinding
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	if resolved, err := asacRegisteredResourceID(c, state, &resource); err != nil || resolved != native {
		t.Fatal("durable origin not resolved", resolved, err)
	}
	state.API = server.URL + "/another-destination"
	if _, err := asacRegisteredResourceID(c, state, &resource); err == nil || output.Normalize(err).Code != 9 {
		t.Fatal("foreign origin adopted", err)
	}
	state.API = server.URL
	if state.Bindings[resource.UID].ResourceID != "" {
		t.Fatal("operation resolution invented an author binding")
	}
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", project, "--output", "json"}
	plan := append([]string{"agent", "@support", "deployment", "plan", "--release", native, "--expected-generation", "7", "--notes", "Activate qualified revision"}, flags...)
	if code, value := invoke(t, plan, ""); code == 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	if code, value := invoke(t, plan, ""); code != 9 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	recover := append([]string{"agent", "@support", "deployment", "reconcile"}, flags...)
	if code, value := invoke(t, recover, ""); code != 9 {
		t.Fatal("foreign receipt accepted", code, value)
	}
	mismatch = false
	if code, value := invoke(t, recover, ""); code != 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	raw, err := c.ReadOperationalFile(asacPrivatePath(c, state, resource.UID, "pending"), 16<<20)
	if err != nil || string(raw) != "{}" {
		t.Fatal("pending not cleared", err)
	}
	if count, err := c.VerifyDeploymentReceipts(resource, true); err != nil || count != 1 {
		t.Fatal("plan mirror not independently verifiable", count, err)
	}
	// A conflicting documentary receipt cannot overwrite immutable evidence.
	if err := c.StoreDeploymentReceipt(resource, server.URL, "workspace", project, receipt, true); err != nil {
		t.Fatal(err)
	}
	receipt["reason"] = "Different audit reason"
	delete(receipt, "plan_digest")
	digest, _ := asac.Digest("deployment-plan", receipt)
	receipt["plan_digest"] = digest
	if err := c.StoreDeploymentReceipt(resource, server.URL, "workspace", project, receipt, true); err == nil {
		t.Fatal("immutable documentary receipt overwritten")
	}
}
