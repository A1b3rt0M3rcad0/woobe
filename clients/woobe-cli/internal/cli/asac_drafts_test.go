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

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

func TestASaCDraftUnknownWriteReconcilesWithoutSecondPUT(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	var c *devworkspace.Config
	var resource devworkspace.Resource
	writes := 0
	operation := ""
	generation := 1
	mismatchedReceipt := true
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var data any
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"asac": map[string]any{"schema_version": "1.0", "isolated_drafts": true, "definition_digest_scope": devworkspace.PortableDefinitionScope}}
		case strings.HasSuffix(r.URL.Path, "/uploads"):
			if err := r.ParseMultipartForm(128 << 20); err != nil {
				t.Error(err)
				return
			}
			defer r.MultipartForm.RemoveAll()
			file, _, err := r.FormFile("file")
			if err != nil {
				t.Error(err)
				return
			}
			defer file.Close()
			bundle, err := packagebundle.ReceiveArchive(file, true)
			if err != nil {
				t.Error(err)
				return
			}
			defer bundle.Close()
			data = map[string]any{"package_schema_version": "1.0", "project_id": "project", "upload_id": "12345678-1234-4321-8321-123456789012", "artifact_digest": bundle.ArtifactDigest, "inventory": bundle.Inventory, "expires_at": time.Now().Add(time.Hour).UTC().Format(time.RFC3339)}
		case r.Method == "PUT":
			writes++
			var body map[string]any
			_ = json.NewDecoder(r.Body).Decode(&body)
			operation = body["operation_id"].(string)
			if body["expected_generation"] != float64(generation) {
				t.Error("lost CAS", body)
			}
			generation++
			// The server committed but failed before its response reached the client.
			w.WriteHeader(500)
			_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "response unavailable"})
			return
		case strings.Contains(r.URL.Path, "/operations/"):
			receiptID := operation
			if mismatchedReceipt {
				receiptID = "12345678-1234-4321-8321-123456789099"
			}
			data = map[string]any{"state": "committed", "operation_id": receiptID, "complete": true, "result": map[string]any{"resource_id": "01a0a033-5820-770c-854b-902864857273", "resource_uid": resource.UID, "draft_id": "12345678-1234-4321-8321-123456789013", "generation": generation, "operation_id": operation, "definition_digest": "sha256:" + strings.Repeat("a", 64), "write_outcome": "committed"}}
		default:
			t.Error("unexpected request", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	var state *devworkspace.State
	c, state, resource = asacWorkspace(t, server.URL)
	observation := asacDraftObservation{ResourceID: state.Bindings[resource.UID].ResourceID, ResourceUID: resource.UID, DraftID: "12345678-1234-4321-8321-123456789013", Generation: 1}
	raw, _ := json.Marshal(observation)
	if err := c.WriteOperationalFile(asacPrivatePath(c, state, resource.UID, "draft"), raw); err != nil {
		t.Fatal(err)
	}
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	run := func(action string) (int, map[string]any) {
		return invoke(t, append([]string{"agent", "@support", "draft", action}, flags...), "")
	}
	if code, value := run("push"); code == 0 {
		t.Fatal("unknown response treated as committed", value)
	}
	if code, value := run("push"); code != 9 || writes != 1 {
		t.Fatal("uncertain write repeated", code, value, writes)
	}
	if code, value := run("reconcile"); code != 9 {
		t.Fatal("Unrelated receipt was accepted", code, value)
	}
	if code, value := run("push"); code != 9 || writes != 1 {
		t.Fatal("Mismatch cleared uncertain write", code, value, writes)
	}
	mismatchedReceipt = false
	if code, value := run("reconcile"); code != 0 {
		t.Fatal(code, value)
	}
	raw, err := c.ReadOperationalFile(asacPrivatePath(c, state, resource.UID, "draft"), 1<<20)
	if err != nil {
		t.Fatal(err)
	}
	var result asacDraftObservation
	_ = json.Unmarshal(raw, &result)
	if result.Generation != float64(2) || writes != 1 {
		t.Fatal("reconcile changed write count or lost generation", result, writes)
	}
	if code, value := run("reconcile"); code != 0 || value["data"].(map[string]any)["pending"] != false || writes != 1 {
		t.Fatal("cleared marker was treated as uncertain", code, value, writes)
	}
}

func TestASaCDraftReconcileCheckpointStates(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	for _, tc := range []struct {
		name, marker string
		code         int
	}{
		{"absent", "", 0}, {"cleared", "{}", 0}, {"whitespace", " { }\n", 0},
		{"null", "null", 9}, {"partial", `{"operation_id":"12345678-1234-4321-8321-123456789013"}`, 9},
		{"invalid", "{", 9}, {"trailing", "{} {}", 9}, {"unknown", `{"unexpected":true}`, 9},
	} {
		t.Run(tc.name, func(t *testing.T) {
			requests := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests++; t.Error("unexpected backend request", r.URL) }))
			defer server.Close()
			c, state, resource := asacWorkspace(t, server.URL)
			if tc.marker != "" {
				if err := c.WriteOperationalFile(asacPrivatePath(c, state, resource.UID, "pending"), []byte(tc.marker)); err != nil {
					t.Fatal(err)
				}
			}
			code, value := invoke(t, []string{"agent", "@support", "draft", "reconcile", "--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}, "")
			if code != tc.code || requests != 0 {
				t.Fatal(code, value, requests)
			}
			if code == 0 && value["data"].(map[string]any)["pending"] != false {
				t.Fatal(value)
			}
		})
	}
}

func TestASaCDraftCheckpointRejectsYAMLChangedAfterSeal(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	writes := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			writes++
			t.Error("changed revision was written")
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"asac": map[string]any{"schema_version": "1.0", "isolated_drafts": true, "definition_digest_scope": devworkspace.PortableDefinitionScope}}})
	}))
	defer server.Close()
	c, state, resource := asacWorkspace(t, server.URL)
	graph, err := devworkspace.LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	record, err := graph.CreateRevision(resource, state, "checkpoint", nil)
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(asacDraftObservation{ResourceID: state.Bindings[resource.UID].ResourceID, ResourceUID: resource.UID, DraftID: "12345678-1234-4321-8321-123456789013", Generation: 1, Definition: record.DefinitionDigest})
	if err = c.WriteOperationalFile(asacPrivatePath(c, state, resource.UID, "draft"), raw); err != nil {
		t.Fatal(err)
	}
	node := graph.Nodes[resource.Key]
	node.Document["metadata"].(map[string]any)["description"] = "edited after sealing"
	raw, err = devworkspace.Encode(node.Document)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(c.RootPath(), node.Descriptor), raw, 0600); err != nil {
		t.Fatal(err)
	}
	code, value := invoke(t, []string{"agent", "@support", "draft", "checkpoint", record.ID, "--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}, "")
	if code != 9 || writes != 0 {
		t.Fatal(code, value, writes)
	}
}

func TestASaCDraftSelectRehydratesPrivateSelectionWithoutMutation(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	var resource devworkspace.Resource
	native := "01a0a033-5820-770c-854b-902864857273"
	draft := "12345678-1234-4321-8321-123456789012"
	wrongUID := false
	writes := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			writes++
			w.WriteHeader(500)
			return
		}
		uid := resource.UID
		if wrongUID {
			uid = "11111111-1111-4111-8111-111111111111"
		}
		line := map[string]any{"draft_id": draft, "resource_id": native, "resource_uid": uid, "generation": 3, "name": "hotfix", "definition_digest": "sha256:" + strings.Repeat("a", 64)}
		var data any = line
		if strings.HasSuffix(r.URL.Path, "/drafts") {
			data = map[string]any{"drafts": []any{line}, "complete": true}
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	c, state, r := asacWorkspace(t, server.URL)
	resource = r
	if err := os.RemoveAll(filepath.Join(c.RootPath(), ".state")); err != nil {
		t.Fatal(err)
	}
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	observation := asacPrivatePath(c, state, resource.UID, "draft")
	code, value := invoke(t, append([]string{"agent", "@support", "draft", "select", "hotfix", "--dry-run"}, flags...), "")
	if code != 0 || value["data"].(map[string]any)["selected"] != false {
		t.Fatal(value)
	}
	if _, err := os.Stat(observation); !os.IsNotExist(err) {
		t.Fatal("dry selection wrote private observation", err)
	}
	wrongUID = true
	code, value = invoke(t, append([]string{"agent", "@support", "draft", "select", "hotfix"}, flags...), "")
	if code != 9 {
		t.Fatal("foreign logical identity selected", value)
	}
	wrongUID = false
	code, value = invoke(t, append([]string{"agent", "@support", "draft", "select", draft}, flags...), "")
	if code != 0 || value["data"].(map[string]any)["selected"] != true {
		t.Fatal(value)
	}
	raw, err := c.ReadOperationalFile(observation, 1<<20)
	if err != nil {
		t.Fatal(err)
	}
	var saved asacDraftObservation
	if json.Unmarshal(raw, &saved) != nil || saved.DraftID != draft || saved.ResourceUID != resource.UID {
		t.Fatal(string(raw))
	}
	pending := asacPrivatePath(c, state, resource.UID, "pending")
	if err = c.WriteOperationalFile(pending, []byte(`{"operation_id":"12345678-1234-4321-8321-123456789013"}`)); err != nil {
		t.Fatal(err)
	}
	code, value = invoke(t, append([]string{"agent", "@support", "draft", "select", "hotfix"}, flags...), "")
	if code != 9 || writes != 0 {
		t.Fatal("unknown operation abandoned or server mutated", value, writes)
	}
}

func TestASaCFreshCloneCannotCreateAnotherRootForKnownOrigin(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests++; t.Error("duplicate guard reached backend") }))
	defer server.Close()
	c, _, _ := asacWorkspace(t, server.URL)
	if err := os.RemoveAll(filepath.Join(c.RootPath(), ".state")); err != nil {
		t.Fatal(err)
	}
	code, value := invoke(t, []string{"agent", "@support", "create", "--yes", "--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}, "")
	if code != 9 || requests != 0 || !strings.Contains(value["error"].(map[string]any)["message"].(string), "duplicate") {
		t.Fatal(value, requests)
	}
}
