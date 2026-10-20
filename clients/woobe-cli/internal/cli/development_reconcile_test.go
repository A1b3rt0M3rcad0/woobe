package cli

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestReconcileUnknownAcceptanceWorksWithBrokenYAMLAndNeverApplies(t *testing.T) {
	t.Chdir(t.TempDir())
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	fingerprint, digest := strings.Repeat("b", 64), strings.Repeat("a", 64)
	lookups := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var data any
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "supported_operations": []string{"sync", "registry"}, "principal_fingerprint": fingerprint}
		case strings.HasSuffix(r.URL.Path, "/operations/lookup"):
			lookups++
			var request map[string]any
			_ = json.NewDecoder(r.Body).Decode(&request)
			if request["idempotency_key"] != "original-key" {
				t.Error("reconciliation changed the accepted key")
			}
			data = map[string]any{"package_schema_version": "1.0", "operation_id": "operation", "project_id": "project", "artifact_digest": digest, "state": "waiting_dependency", "terminal": false, "revision": 2, "phases_completed": 1, "phases_total": 3}
		default:
			t.Error("reconciliation attempted unexpected request", r.Method, r.URL.Path)
			w.WriteHeader(500)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	c, err := devworkspace.Create(".", ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	uid, _ := devworkspace.NewID()
	c.Resources = []devworkspace.Resource{{UID: uid, Kind: "Agent", Key: "support", Alias: "support", Path: "agents/support"}}
	if err := c.Save(); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(c.RootPath(), ".state", "pending.json")
	store, err := packagecheckpoint.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	cp := packagecheckpoint.Checkpoint{Format: "woobe-package-checkpoint", SchemaVersion: "1.0", APIOrigin: server.URL, ProjectID: "project", ArtifactDigest: digest, UploadID: "upload", PlanID: "plan", PlanDigest: digest, IdempotencyKey: "original-key", PrincipalFingerprint: fingerprint, RequestIdentity: digest, Lifecycle: "draft", State: packagecheckpoint.OutcomeUnknown, CreatedAt: now, UpdatedAt: now}
	if err := store.Save(cp); err != nil {
		t.Fatal(err)
	}
	store.Close()
	state, err := c.ReadState(server.URL, "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	state.Pending = map[string]string{uid: path}
	if err := c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	broken := filepath.Join(c.RootPath(), "agents/support/agent.yaml")
	if err := os.MkdirAll(filepath.Dir(broken), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(broken, []byte("broken: ["), 0600); err != nil {
		t.Fatal(err)
	}
	code, response := invoke(t, []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "agent", "@support", "reconcile", "--output", "json"}, "")
	if code != 0 || response["data"].(map[string]any)["pending"] != true || lookups != 1 {
		t.Fatal(code, response, lookups)
	}
	hint := response["data"].(map[string]any)["next_command"].(string)
	if hint != "woobe package status operation" {
		t.Fatal("reconciliation suggested an unavailable command", hint)
	}
	app := New(strings.NewReader(""), io.Discard, io.Discard)
	command, _, err := app.Root.Find(strings.Fields(hint)[1:])
	if err != nil || command.CommandPath() != "woobe package status" {
		t.Fatal("suggested observation command is not available", err)
	}
	data, _ := os.ReadFile(broken)
	if string(data) != "broken: [" {
		t.Fatal("reconciliation rewrote author files")
	}
}
