package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestPackageStatusKeepsAcceptedOperationIncomplete(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control-key")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data := map[string]any{"package_schema_version": "1.0"}
		if strings.HasSuffix(r.URL.Path, "/capabilities") {
			data["schema_catalog_sha256"] = packagefmt.CatalogDigest()
			data["supported_operations"] = []string{"status"}
		} else {
			data["operation_id"] = "operation"
			data["project_id"] = "project"
			data["state"] = "accepted"
			data["terminal"] = false
			data["revision"] = 1
			data["phases_completed"] = 0
			data["phases_total"] = 3
			data["artifact_digest"] = strings.Repeat("a", 64)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"package", "status", "operation", "--api-url", server.URL, "--project", "project"}, "")
	if code != 0 || result["success"] != true || result["meta"].(map[string]any)["complete"] != false || result["data"].(map[string]any)["state"] != "accepted" {
		t.Fatal(code, result)
	}
}

func TestPackageUnsupportedServerCannotReceiveCancellation(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control-key")
	var mutations atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			mutations.Add(1)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": "incompatible", "supported_operations": []string{"cancel"}}})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"package", "cancel", "operation", "--api-url", server.URL, "--project", "project"}, "")
	if code != 9 || mutations.Load() != 0 {
		t.Fatal(code, result, mutations.Load())
	}
}

func TestPackageResumeRequiresObservedRevisionBeforeCredentials(t *testing.T) {
	code, result := invoke(t, []string{"package", "resume", "operation", "--credential", "missing"}, "")
	if code != 2 {
		t.Fatal(code, result)
	}
}

func TestPackageJSONLWaitEndsWithOneOrderedFinalRecord(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control-key")
	var reads atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data := map[string]any{"package_schema_version": "1.0"}
		if strings.HasSuffix(r.URL.Path, "/capabilities") {
			data["schema_catalog_sha256"] = packagefmt.CatalogDigest()
			data["supported_operations"] = []string{"status"}
		} else {
			terminal := reads.Add(1) > 1
			state, completed := "accepted", 0
			if terminal {
				state, completed = "succeeded", 1
			}
			data = map[string]any{"package_schema_version": "1.0", "operation_id": "operation", "project_id": "project", "artifact_digest": strings.Repeat("a", 64), "state": state, "terminal": terminal, "revision": reads.Load(), "phases_completed": completed, "phases_total": 1, "next_poll_after_ms": 1}
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	out := &bytes.Buffer{}
	app := New(strings.NewReader(""), out, &bytes.Buffer{})
	code := app.Execute(context.Background(), []string{"package", "status", "operation", "--wait", "--output", "jsonl", "--api-url", server.URL, "--project", "project", "--config", filepath.Join(t.TempDir(), "config.json")})
	if code != 0 {
		t.Fatalf("wait failed: %s", out)
	}
	lines := bytes.Split(bytes.TrimSpace(out.Bytes()), []byte("\n"))
	if len(lines) < 2 {
		t.Fatal("no progress and final records")
	}
	for index, line := range lines {
		var record map[string]any
		if err := json.Unmarshal(line, &record); err != nil {
			t.Fatal(err)
		}
		meta := record["meta"].(map[string]any)
		if meta["sequence"] != float64(index+1) || meta["operation_id"] != "operation" {
			t.Fatal("unordered or unscoped progress")
		}
		if (meta["record"] == "final") != (index == len(lines)-1) {
			t.Fatal("final record not last and unique")
		}
	}
}

func TestPackageStatusRecoversUnknownCheckpointWithoutApply(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control-key")
	digest, fingerprint := strings.Repeat("a", 64), strings.Repeat("b", 64)
	var lookups atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data := map[string]any{"package_schema_version": "1.0"}
		if strings.HasSuffix(r.URL.Path, "/capabilities") {
			data["schema_catalog_sha256"] = packagefmt.CatalogDigest()
			data["supported_operations"] = []string{"status"}
			data["principal_fingerprint"] = fingerprint
		} else if strings.HasSuffix(r.URL.Path, "/operations/lookup") {
			var body map[string]any
			_ = json.NewDecoder(r.Body).Decode(&body)
			if body["idempotency_key"] != "package-original" {
				t.Error("lookup identity changed")
			}
			lookups.Add(1)
			data = map[string]any{"package_schema_version": "1.0", "operation_id": "operation", "project_id": "project", "artifact_digest": digest, "state": "accepted", "terminal": false, "revision": 1, "phases_completed": 0, "phases_total": 1}
		} else {
			t.Errorf("unexpected request %s %s", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	path := filepath.Join(t.TempDir(), "checkpoint.json")
	store, err := packagecheckpoint.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	checkpoint := packagecheckpoint.Checkpoint{Format: "woobe-package-checkpoint", SchemaVersion: "1.0", APIOrigin: server.URL, ProjectID: "project", ArtifactDigest: digest, UploadID: "upload", PlanID: "plan", PlanDigest: digest, IdempotencyKey: "package-original", PrincipalFingerprint: fingerprint, RequestIdentity: digest, Lifecycle: "draft", State: packagecheckpoint.OutcomeUnknown, CreatedAt: now, UpdatedAt: now}
	if err := store.Save(checkpoint); err != nil {
		t.Fatal(err)
	}
	store.Close()
	code, result := invoke(t, []string{"package", "status", "--checkpoint", path, "--api-url", server.URL, "--project", "project"}, "")
	if code != 0 || lookups.Load() != 1 || result["data"].(map[string]any)["operation_id"] != "operation" {
		t.Fatal(code, result)
	}
	store, err = packagecheckpoint.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	observed, err := store.Read()
	if err != nil || observed.OperationID != "operation" || observed.State != packagecheckpoint.Observing || observed.IdempotencyKey != "package-original" {
		t.Fatal("original operation was not durably recovered", err)
	}
}
