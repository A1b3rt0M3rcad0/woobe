package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
)

func TestExactPublicationLostAcceptanceAndDocumentaryFailureNeverRepublish(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	const native = "01a0a033-5820-770c-854b-902864857273"
	const project = "12345678-1234-4321-8321-123456789012"
	const candidate = "12345678-1234-4321-8321-123456789014"
	const evaluation = "12345678-1234-4321-8321-123456789015"
	const publication = "12345678-1234-4321-8321-123456789016"
	const released = "12345678-1234-4321-8321-123456789017"
	var resource devworkspace.Resource
	var receipt map[string]any
	writes := 0
	hash := "sha256:" + strings.Repeat("d", 64)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var data any
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"asac": map[string]any{"schema_version": "1.0", "candidate_publication_kinds": []any{"Agent"}}}
		case strings.HasSuffix(r.URL.Path, "/candidates/"+candidate):
			data = map[string]any{"candidate_id": candidate, "resource_id": native, "resource_uid": resource.UID, "state": "ready", "record_digest": hash, "runtime_digest": hash}
		case strings.HasSuffix(r.URL.Path, "/evaluations/"+evaluation):
			data = map[string]any{"evaluation_id": evaluation, "candidate_id": candidate, "resource_id": native, "state": "passed", "record_digest": hash, "runtime_digest": hash}
		case r.Method == "POST" && strings.HasSuffix(r.URL.Path, "/publications"):
			writes++
			var body map[string]any
			_ = json.NewDecoder(r.Body).Decode(&body)
			if len(body) != 4 || body["candidate_id"] != candidate || body["evaluation_id"] != evaluation {
				t.Error("Publication inferred current Staging or added authority", body)
			}
			receipt = map[string]any{"schema_version": "1.0", "kind": "Agent", "publication_id": publication, "project_id": project, "resource_id": native, "resource_uid": resource.UID, "operation_id": body["operation_id"], "write_outcome": "committed", "state": "published", "candidate_id": candidate, "evaluation_id": evaluation, "release_id": released, "release_version": "v0.0.20261009.01", "revision_id": "rv_12345678-1234-4321-8321-123456789019", "reused": false, "actor": "control:12345678-1234-4321-8321-123456789011", "reason": body["reason"], "created_at": "2026-10-09T00:00:00+00:00", "git": map[string]any{"status": "unavailable"}, "published": true, "production_changed": false, "complete": true}
			for _, key := range []string{"record_digest", "runtime_digest", "definition_digest", "artifact_digest", "binding_digest", "suite_digest", "dataset_digest", "policy_digest"} {
				receipt[key] = hash
			}
			digest, err := asac.Digest("publication-receipt", receipt)
			if err != nil {
				t.Error(err)
			}
			receipt["receipt_digest"] = digest
			w.WriteHeader(500)
			_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "lost after publication"})
			return
		case strings.Contains(r.URL.Path, "/operations/"):
			data = map[string]any{"operation_id": receipt["operation_id"], "state": "committed", "result": receipt}
		case r.Method == "GET" && strings.HasSuffix(r.URL.Path, "/publications/"+publication):
			data = receipt
		default:
			t.Error("Publication changed an environment or touched current Staging", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	c, state, resource := asacWorkspace(t, server.URL)
	state.Project = project
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	flags := []string{"--api-url", server.URL, "--project", project, "--workspace", "workspace", "--output", "json"}
	publish := append([]string{"agent", "@support", "publish", "--candidate", candidate, "--evaluation", evaluation, "--notes", "Qualified release", "--yes"}, flags...)
	if code, value := invoke(t, append(publish, "--dry-run"), ""); code != 0 || writes != 0 {
		t.Fatal(code, value, writes)
	}
	if code, value := invoke(t, publish, ""); code == 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	if code, value := invoke(t, publish, ""); code != 9 || writes != 1 {
		t.Fatal("Unknown publication repeated", code, value, writes)
	}
	descriptor, err := c.ResourcePath(resource)
	if err != nil {
		t.Fatal(err)
	}
	historyDir := strings.TrimSuffix(descriptor, filepath.Ext(descriptor)) + ".asac"
	blocked := filepath.Join(historyDir, "publications")
	if err = os.MkdirAll(historyDir, 0700); err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(blocked, []byte("blocked"), 0600); err != nil {
		t.Fatal(err)
	}
	reconcile := append([]string{"agent", "@support", "draft", "reconcile"}, flags...)
	if code, value := invoke(t, reconcile, ""); code != 10 || writes != 1 {
		t.Fatal("Documentary error cleared original operation", code, value, writes)
	}
	if err = os.Remove(blocked); err != nil {
		t.Fatal(err)
	}
	if code, value := invoke(t, reconcile, ""); code != 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	files, err := filepath.Glob(filepath.Join(blocked, "*.yaml"))
	if err != nil || len(files) != 1 {
		t.Fatal("Missing append-only publication", files, err)
	}
	if code, value := invoke(t, append([]string{"agent", native, "publication", publication, "--no-project-config"}, flags...), ""); code != 0 {
		t.Fatal(code, value)
	}
	if count, verifyErr := c.VerifyPublicationReceipts(resource); verifyErr != nil || count != 1 {
		t.Fatal("Publication mirror did not verify", count, verifyErr)
	}
	if err = c.StorePublicationReceipt(resource, server.URL, "workspace", project, receipt); err != nil {
		t.Fatal("Identical receipt cannot be replayed", err)
	}
	changed := make(map[string]any, len(receipt))
	for key, value := range receipt {
		changed[key] = value
	}
	changed["reason"] = "Different audit reason"
	delete(changed, "receipt_digest")
	changed["receipt_digest"], err = asac.Digest("publication-receipt", changed)
	if err != nil {
		t.Fatal(err)
	}
	if err = c.StorePublicationReceipt(resource, server.URL, "workspace", project, changed); err == nil {
		t.Fatal("An immutable publication was replaced")
	}
	original, err := os.ReadFile(files[0])
	if err != nil {
		t.Fatal(err)
	}
	tampered := strings.Replace(string(original), "Qualified release", "Tampered release", 1)
	if tampered == string(original) {
		t.Fatal("Tamper fixture did not change receipt")
	}
	if err = os.WriteFile(files[0], []byte(tampered), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = c.VerifyPublicationReceipts(resource); err == nil {
		t.Fatal("Corrupt documentary publication accepted")
	}
}

func TestExactPublicationRejectsAmbiguousOrMissingIdentity(t *testing.T) {
	for _, args := range [][]string{
		{"agent", "id", "publish", "--candidate", "", "--evaluation", "", "--yes"},
		{"agent", "id", "stage", "--candidate", "12345678-1234-4321-8321-123456789014"},
		{"agent", "id", "publish", "--candidate", "12345678-1234-4321-8321-123456789014", "--version", "v1"},
	} {
		if code, value := invoke(t, args, ""); code != 2 {
			t.Fatal(code, value)
		}
	}
}
