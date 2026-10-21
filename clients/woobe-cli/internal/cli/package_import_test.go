package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestPackageImportLostResponseReconcilesWithoutResending(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	var posts atomic.Int32
	var acceptedKey string
	digest := strings.Repeat("a", 64)
	operation := map[string]any{"package_schema_version": "1.0", "operation_id": "operation", "project_id": "project", "artifact_digest": digest, "state": "accepted", "terminal": false, "revision": 1, "phases_completed": 0, "phases_total": 3}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data := map[string]any{}
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "supported_operations": []string{"apply"}, "principal_fingerprint": strings.Repeat("b", 64)}
		case strings.HasSuffix(r.URL.Path, "/apply"):
			posts.Add(1)
			acceptedKey = r.Header.Get("Idempotency-Key")
			connection, _, err := w.(http.Hijacker).Hijack()
			if err != nil {
				t.Error(err)
				return
			}
			_ = connection.Close()
			return
		case strings.HasSuffix(r.URL.Path, "/operations/lookup"):
			var request struct {
				Key string `json:"idempotency_key"`
			}
			_ = json.NewDecoder(r.Body).Decode(&request)
			if request.Key != acceptedKey {
				t.Error("lookup changed the accepted key")
			}
			data = operation
		default:
			t.Error(r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	directory := t.TempDir()
	planPath := filepath.Join(directory, "plan.json")
	checkpoint := filepath.Join(directory, "checkpoint.json")
	receipt := packageapi.PlanReceipt{Format: "woobe-package-plan-receipt", SchemaVersion: "1.0", PrincipalFingerprint: strings.Repeat("b", 64), Plan: packageapi.Plan{PackageSchemaVersion: "1.0", APIOrigin: server.URL, ProjectID: "project", UploadID: "upload", PlanID: "plan", PlanDigest: digest, ArtifactDigest: digest, DefinitionDigest: digest, CapabilitiesDigest: digest, BindingsDigest: digest, Lifecycle: "draft", CreatedAt: time.Now().UTC().Format(time.RFC3339Nano), ExpiresAt: time.Now().Add(time.Hour).UTC().Format(time.RFC3339Nano), Effects: []packageapi.Effect{{Key: "agent:x", Owner: "agent", Action: "prepare_inactive_agent", Permission: "agent:write"}}, Bindings: map[string]any{"format": "woobe-package", "schema_version": "1.0", "kind": "ImportBindings", "metadata": map[string]any{"name": "Destination"}, "spec": map[string]any{}}}}
	receipt.Plan.BindingsDigest, _ = packageapi.BindingsDigest(receipt.Plan.Bindings)
	if err := receipt.Save(planPath); err != nil {
		t.Fatal(err)
	}
	args := []string{"package", "import", "--plan-file", planPath, "--checkpoint", checkpoint, "--api-url", server.URL, "--project", "project"}
	code, result := invoke(t, args, "")
	if code != 9 || posts.Load() != 1 {
		t.Fatal(code, result, posts.Load())
	}
	// Reconciliation succeeds even if the protected store would now be unavailable.
	code, result = invoke(t, args, "")
	if code != 0 || posts.Load() != 1 || result["meta"].(map[string]any)["complete"] != false {
		t.Fatal(code, result, posts.Load())
	}
	store, err := packagecheckpoint.Open(checkpoint)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	cp, err := store.Read()
	if err != nil || cp.OperationID != "operation" || cp.IdempotencyKey != acceptedKey || cp.State != packagecheckpoint.Observing {
		t.Fatal(cp, err)
	}
}

func TestPackageImportAutomaticCheckpointLostResponseReconcilesWithoutResending(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	var posts atomic.Int32
	var acceptedKey string
	digest := strings.Repeat("a", 64)
	operation := map[string]any{"package_schema_version": "1.0", "operation_id": "operation", "project_id": "project", "artifact_digest": digest, "state": "accepted", "terminal": false, "revision": 1, "phases_completed": 0, "phases_total": 3}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data := map[string]any{}
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "supported_operations": []string{"apply"}, "principal_fingerprint": strings.Repeat("b", 64)}
		case strings.HasSuffix(r.URL.Path, "/apply"):
			posts.Add(1)
			acceptedKey = r.Header.Get("Idempotency-Key")
			connection, _, err := w.(http.Hijacker).Hijack()
			if err != nil {
				t.Error(err)
				return
			}
			_ = connection.Close()
			return
		case strings.HasSuffix(r.URL.Path, "/operations/lookup"):
			var request struct {
				Key string `json:"idempotency_key"`
			}
			_ = json.NewDecoder(r.Body).Decode(&request)
			if request.Key != acceptedKey {
				t.Error("lookup changed the accepted key")
			}
			data = operation
		default:
			t.Error(r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	directory := t.TempDir()
	planPath := filepath.Join(directory, "plan.json")
	checkpoint := filepath.Join(directory, "checkpoint.json")
	receipt := packageapi.PlanReceipt{Format: "woobe-package-plan-receipt", SchemaVersion: "1.0", PrincipalFingerprint: strings.Repeat("b", 64), Plan: packageapi.Plan{PackageSchemaVersion: "1.0", APIOrigin: server.URL, ProjectID: "project", UploadID: "upload", PlanID: "plan", PlanDigest: digest, ArtifactDigest: digest, DefinitionDigest: digest, CapabilitiesDigest: digest, BindingsDigest: digest, Lifecycle: "draft", CreatedAt: time.Now().UTC().Format(time.RFC3339Nano), ExpiresAt: time.Now().Add(time.Hour).UTC().Format(time.RFC3339Nano), Effects: []packageapi.Effect{{Key: "agent:x", Owner: "agent", Action: "prepare_inactive_agent", Permission: "agent:write"}}, Bindings: map[string]any{"format": "woobe-package", "schema_version": "1.0", "kind": "ImportBindings", "metadata": map[string]any{"name": "Destination"}, "spec": map[string]any{}}}}
	receipt.Plan.BindingsDigest, _ = packageapi.BindingsDigest(receipt.Plan.Bindings)
	if err := receipt.Save(planPath); err != nil {
		t.Fatal(err)
	}
	args := []string{"package", "import", "--plan-file", planPath, "--api-url", server.URL, "--project", "project"}
	code, result := packageStableInvoke(t, args, filepath.Join(directory, "config.json"))
	if code != 9 || posts.Load() != 1 {
		t.Fatal(code, result, posts.Load())
	}
	// Reconciliation succeeds even if the protected store would now be unavailable.
	checkpoint = result["meta"].(map[string]any)["checkpoint"].(string)
	code, result = packageStableInvoke(t, args, filepath.Join(directory, "config.json"))
	if code != 0 || posts.Load() != 1 || result["meta"].(map[string]any)["complete"] != false {
		t.Fatal(code, result, posts.Load())
	}
	store, err := packagecheckpoint.Open(checkpoint)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	cp, err := store.Read()
	if err != nil || cp.OperationID != "operation" || cp.IdempotencyKey != acceptedKey || cp.State != packagecheckpoint.Observing {
		t.Fatal(cp, err)
	}
}

func TestPackageImportOfflineAndFlagErrorsNeverContactServer(t *testing.T) {
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { requests.Add(1) }))
	defer server.Close()
	code, result := invoke(t, []string{"package", "import", localPackageFixture(t), "--bind", packageBindingShortcut, "--dry-run", "--api-url", server.URL, "--credential", "missing"}, "")
	if code != 0 || requests.Load() != 0 || result["data"].(map[string]any)["executed"] != false {
		t.Fatal(code, result)
	}
	code, result = invoke(t, []string{"package", "import", localPackageFixture(t), "--plan-file", "missing", "--checkpoint", "missing", "--api-url", server.URL}, "")
	if code != 2 || requests.Load() != 0 {
		t.Fatal(code, result)
	}
}

func TestPackagePreparedCheckpointRejectsChangedSourceBindingsAndLifecycle(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	var writes atomic.Int32
	fingerprint := strings.Repeat("b", 64)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/capabilities") {
			writes.Add(1)
			t.Error("unexpected request", r.URL.Path)
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "supported_operations": []string{"apply"}, "principal_fingerprint": fingerprint}})
	}))
	defer server.Close()
	for _, scenario := range []string{"source", "bindings", "lifecycle"} {
		t.Run(scenario, func(t *testing.T) {
			source := localPackageFixture(t)
			bundle, err := packagebundle.Load(source, false)
			if err != nil {
				t.Fatal(err)
			}
			defer bundle.Close()
			bindings, err := packagefmt.LoadBindings("", []string{packageBindingShortcut}, bundle.Graph)
			if err != nil {
				t.Fatal(err)
			}
			digest, err := packageapi.BindingsDigest(bindings)
			if err != nil {
				t.Fatal(err)
			}
			now := time.Now().UTC()
			fixed := strings.Repeat("a", 64)
			receipt := packageapi.PlanReceipt{Format: "woobe-package-plan-receipt", SchemaVersion: "1.0", PrincipalFingerprint: fingerprint, Plan: packageapi.Plan{PackageSchemaVersion: "1.0", APIOrigin: server.URL, ProjectID: "project", UploadID: "upload", PlanID: "plan", PlanDigest: fixed, ArtifactDigest: bundle.ArtifactDigest, DefinitionDigest: fixed, CapabilitiesDigest: fixed, BindingsDigest: digest, Lifecycle: "draft", CreatedAt: now.Format(time.RFC3339Nano), ExpiresAt: now.Add(time.Hour).Format(time.RFC3339Nano), Effects: []packageapi.Effect{{Key: "agent:x", Owner: "agent", Action: "prepare_inactive_agent", Permission: "agent:write"}}, Bindings: bindings}}
			checkpoint := filepath.Join(t.TempDir(), "checkpoint.json")
			if err = receipt.Save(checkpoint + ".plan.json"); err != nil {
				t.Fatal(err)
			}
			store, err := packagecheckpoint.Open(checkpoint)
			if err != nil {
				t.Fatal(err)
			}
			cp := packagecheckpoint.Checkpoint{Format: "woobe-package-checkpoint", SchemaVersion: "1.0", APIOrigin: server.URL, ProjectID: "project", ArtifactDigest: bundle.ArtifactDigest, UploadID: "upload", PlanID: "plan", PlanDigest: fixed, IdempotencyKey: "original-key", PrincipalFingerprint: fingerprint, RequestIdentity: fixed, Lifecycle: "draft", State: packagecheckpoint.Prepared, CreatedAt: now, UpdatedAt: now}
			if err = store.Save(cp); err != nil {
				t.Fatal(err)
			}
			store.Close()
			args := []string{"package", "import", source, "--checkpoint", checkpoint, "--api-url", server.URL, "--project", "project"}
			switch scenario {
			case "source":
				file, err := os.OpenFile(filepath.Join(source, "agent.yaml"), os.O_APPEND|os.O_WRONLY, 0600)
				if err != nil {
					t.Fatal(err)
				}
				file.WriteString("\n")
				file.Close()
			case "bindings":
				args = append(args, "--bind", "credential.primary-key=00000000-0000-4000-8000-000000000002")
			case "lifecycle":
				args = append(args, "--lifecycle", "staging")
			}
			code, result := invoke(t, args, "")
			if code != 2 || writes.Load() != 0 {
				t.Fatal(code, result, writes.Load())
			}
		})
	}
}

func TestPackageImportPreservesRejectionAndDeadlineWithoutReplay(t *testing.T) {
	for _, scenario := range []struct {
		name    string
		status  int
		code    int
		outcome string
	}{
		{"forbidden", http.StatusForbidden, 4, "rejected"},
		{"stale", http.StatusConflict, 6, "rejected"},
		{"deadline", 0, 8, "unknown"},
	} {
		t.Run(scenario.name, func(t *testing.T) {
			t.Setenv("WOOBE_CONTROL_KEY", "test-control")
			var posts atomic.Int32
			digest := strings.Repeat("a", 64)
			fingerprint := strings.Repeat("b", 64)
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if strings.HasSuffix(r.URL.Path, "/capabilities") {
					json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "supported_operations": []string{"apply"}, "principal_fingerprint": fingerprint}})
					return
				}
				if strings.HasSuffix(r.URL.Path, "/apply") {
					posts.Add(1)
					if scenario.status == 0 {
						// Hold the accepted request until the client's deadline instead
						// of racing a short sleep against runner scheduling.
						select {
						case <-r.Context().Done():
						case <-time.After(10 * time.Second):
						}
						return
					}
					w.WriteHeader(scenario.status)
					json.NewEncoder(w).Encode(map[string]any{"success": false, "data": map[string]any{"package_schema_version": "1.0", "diagnostics": []any{map[string]any{"code": "PACKAGE_PLAN_STALE", "message": "private-provider-value"}}}})
					return
				}
				// A repeated invocation may reconcile, but must not resend Apply.
				w.WriteHeader(http.StatusNotFound)
			}))
			defer server.Close()
			directory := t.TempDir()
			planPath := filepath.Join(directory, "plan.json")
			checkpoint := filepath.Join(directory, "checkpoint.json")
			receipt := packageapi.PlanReceipt{Format: "woobe-package-plan-receipt", SchemaVersion: "1.0", PrincipalFingerprint: fingerprint, Plan: packageapi.Plan{PackageSchemaVersion: "1.0", APIOrigin: server.URL, ProjectID: "project", UploadID: "upload", PlanID: "plan", PlanDigest: digest, ArtifactDigest: digest, DefinitionDigest: digest, CapabilitiesDigest: digest, Lifecycle: "draft", CreatedAt: time.Now().UTC().Format(time.RFC3339Nano), ExpiresAt: time.Now().Add(time.Hour).UTC().Format(time.RFC3339Nano), Effects: []packageapi.Effect{{Key: "agent:x", Owner: "agent", Action: "prepare_inactive_agent", Permission: "agent:write"}}, Bindings: map[string]any{"format": "woobe-package", "schema_version": "1.0", "kind": "ImportBindings", "metadata": map[string]any{"name": "Destination"}, "spec": map[string]any{}}}}
			receipt.Plan.BindingsDigest, _ = packageapi.BindingsDigest(receipt.Plan.Bindings)
			if err := receipt.Save(planPath); err != nil {
				t.Fatal(err)
			}
			timeout := "30s"
			if scenario.status == 0 {
				// Allow capability discovery and checkpoint I/O to reach Apply
				// even on a busy native runner before testing deadline expiry.
				timeout = "5s"
			}
			args := []string{"package", "import", "--plan-file", planPath, "--checkpoint", checkpoint, "--api-url", server.URL, "--project", "project", "--wait-timeout", timeout}
			code, result := invoke(t, args, "")
			failure := result["error"].(map[string]any)
			if code != scenario.code || failure["write_outcome"] != scenario.outcome || posts.Load() != 1 || strings.Contains(failure["message"].(string), "private-provider-value") {
				t.Fatal(code, result, posts.Load())
			}
			if scenario.status != 0 && (failure["domain_code"] != "PACKAGE_PLAN_STALE" || failure["http_status"] != float64(scenario.status)) {
				t.Fatal(result)
			}
			invoke(t, args, "")
			if posts.Load() != 1 {
				t.Fatal("Apply replayed")
			}
		})
	}
}
