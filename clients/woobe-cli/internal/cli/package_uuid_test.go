package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestPackageStatusUUIDCaseWithAndWithoutCheckpoint(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control-key")
	const project = "01a00d46-1ed7-71f7-99a4-aaa2cf81637c"
	const operation = "01a0a033-7ef9-7776-bdd2-2ba5b782843e"
	digest, fingerprint := strings.Repeat("a", 64), strings.Repeat("b", 64)
	for _, scope := range []string{"project", "operation", "both"} {
		for _, checkpoint := range []bool{false, true} {
			name := scope
			if checkpoint {
				name += "/checkpoint"
			}
			t.Run(name, func(t *testing.T) {
				server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					data := map[string]any{"package_schema_version": "1.0"}
					switch r.URL.Path {
					case "/projects/" + project + "/packages/capabilities":
						data["schema_catalog_sha256"] = packagefmt.CatalogDigest()
						data["supported_operations"] = []string{"status"}
						data["principal_fingerprint"] = fingerprint
					case "/projects/" + project + "/packages/operations/" + operation:
						data = map[string]any{"package_schema_version": "1.0", "operation_id": operation, "project_id": project, "artifact_digest": digest, "state": "accepted", "terminal": false, "revision": 1, "phases_completed": 0, "phases_total": 3}
					default:
						t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
					}
					_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
				}))
				defer server.Close()
				projectInput, operationInput := project, operation
				if scope == "project" || scope == "both" {
					projectInput = strings.ToUpper(project)
				}
				if scope == "operation" || scope == "both" {
					operationInput = strings.ToUpper(operation)
				}
				args := []string{"package", "status", operationInput, "--api-url", server.URL, "--project", projectInput}
				if checkpoint {
					path := filepath.Join(t.TempDir(), "checkpoint.json")
					store, err := packagecheckpoint.Open(path)
					if err != nil {
						t.Fatal(err)
					}
					now := time.Now().UTC()
					cp := packagecheckpoint.Checkpoint{Format: "woobe-package-checkpoint", SchemaVersion: "1.0", APIOrigin: server.URL, ProjectID: project, ArtifactDigest: digest, UploadID: "upload", PlanID: "plan", PlanDigest: digest, IdempotencyKey: "original-key", PrincipalFingerprint: fingerprint, RequestIdentity: digest, Lifecycle: "draft", OperationID: operation, LastRevision: 1, LastRemoteState: "accepted", State: packagecheckpoint.Observing, CreatedAt: now, UpdatedAt: now}
					if err := store.Save(cp); err != nil {
						t.Fatal(err)
					}
					store.Close()
					args = append(args, "--checkpoint", path)
				}
				code, result := invoke(t, args, "")
				if code != 0 || result["success"] != true || result["data"].(map[string]any)["operation_id"] != operation || result["meta"].(map[string]any)["complete"] != false {
					t.Fatal(code, result)
				}
			})
		}
	}
}
