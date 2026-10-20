package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestCandidateStageSealedObjectLostAcceptanceDoesNotRepeatWrite(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	var resource devworkspace.Resource
	var record *devworkspace.Revision
	var receipt map[string]any
	writes := 0
	const draft = "12345678-1234-4321-8321-123456789013"
	const native = "01a0a033-5820-770c-854b-902864857273"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var data any
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"asac": map[string]any{"schema_version": "1.0", "candidate_preparation": true}}
		case strings.Contains(r.URL.Path, "/drafts/"):
			data = map[string]any{"resource_id": native, "resource_uid": resource.UID, "draft_id": draft,
				"generation": 1, "working_revision_id": record.ID, "definition_digest": record.DefinitionDigest}
		case strings.Contains(r.URL.Path, "/revisions/"):
			data = map[string]any{"record": record}
		case r.Method == "POST" && strings.HasSuffix(r.URL.Path, "/candidates"):
			writes++
			var body map[string]any
			if json.NewDecoder(r.Body).Decode(&body) != nil {
				t.Error("missing Stage body")
			}
			if body["revision_id"] != record.ID || body["draft_id"] != draft || body["expected_generation"] != float64(1) {
				t.Error("Stage changed sealed source selection")
			}
			receipt = map[string]any{"operation_id": body["operation_id"], "write_outcome": "committed",
				"candidate_id": "12345678-1234-4321-8321-123456789014", "preparation_operation_id": "12345678-1234-4321-8321-123456789015",
				"resource_id": native, "resource_uid": resource.UID, "draft_id": draft, "draft_generation": 1,
				"revision_id": record.ID, "record_digest": record.RecordDigest, "state": "preparing", "published": false, "production_changed": false, "complete": false}
			w.WriteHeader(500)
			_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "response lost after commit"})
			return
		case strings.Contains(r.URL.Path, "/operations/"):
			data = map[string]any{"operation_id": receipt["operation_id"], "state": "committed", "result": receipt}
		default:
			t.Error("Stage touched a singleton or unrelated resource", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	c, state, resource := asacWorkspace(t, server.URL)
	graph, err := devworkspace.LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	record, err = graph.CreateRevision(resource, state, "Exact candidate source", nil)
	if err != nil {
		t.Fatal(err)
	}
	bundle, err := c.OpenExecutableObject(resource, *record)
	if err != nil {
		t.Fatal(err)
	}
	for _, raw := range packagefmt.List(packagefmt.Object(packagefmt.Object(bundle.Graph.Manifest["spec"])["requires"])["credentials"]) {
		state.Credentials[packagefmt.Text(packagefmt.Object(raw)["ref"])] = "12345678-1234-4321-8321-123456789016"
	}
	bundle.Close()
	if err = c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(asacDraftObservation{ResourceID: native, ResourceUID: resource.UID, DraftID: draft, Generation: 1, Definition: record.DefinitionDigest})
	if err = c.WriteOperationalFile(asacPrivatePath(c, state, resource.UID, "draft"), raw); err != nil {
		t.Fatal(err)
	}
	// Deliberately invalid current YAML must not replace the sealed object.
	descriptor, _ := c.ResourcePath(resource)
	if err = os.WriteFile(descriptor, []byte("invalid: [current author edit\n"), 0600); err != nil {
		t.Fatal(err)
	}
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	stage := append([]string{"agent", "@support", "stage", "--revision", record.ID, "--yes"}, flags...)
	if code, value := invoke(t, append(stage, "--dry-run"), ""); code != 0 || writes != 0 {
		t.Fatal(code, value, writes)
	}
	if code, value := invoke(t, stage, ""); code == 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	if code, value := invoke(t, stage, ""); code != 9 || writes != 1 {
		t.Fatal("unknown Stage repeated", code, value, writes)
	}
	if code, value := invoke(t, append([]string{"agent", "@support", "draft", "reconcile"}, flags...), ""); code != 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	raw, err = c.ReadOperationalFile(asacPrivatePath(c, state, resource.UID, "draft"), 1<<20)
	if err != nil {
		t.Fatal(err)
	}
	var observed asacDraftObservation
	_ = json.Unmarshal(raw, &observed)
	if observed.Generation != float64(1) {
		t.Fatal("Stage reconciliation replaced Draft CAS", observed)
	}
	raw, err = c.ReadOperationalFile(asacPrivatePath(c, state, resource.UID, "candidate"), 1<<20)
	if err != nil || !strings.Contains(string(raw), receipt["candidate_id"].(string)) {
		t.Fatal("lost original Candidate identity", err)
	}
}

func TestCandidateBindingAndAcceptanceRejectIncompleteEvidence(t *testing.T) {
	if _, err := candidateBindings(map[string]any{"credentials": []any{map[string]any{"ref": "provider"}}}, map[string]string{}); err == nil {
		t.Fatal("Stage inferred an unknown credential")
	}
	if err := validateCandidateAcceptance(map[string]any{}, "op", "id", "uid", "revision", "draft", "digest"); err == nil {
		t.Fatal("Incomplete acceptance cleared unknown write")
	}
}

func TestCandidateInspectionUnwrapsAndValidatesOwnerScope(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	const root = "12345678-1234-4321-8321-123456789013"
	const candidate = "12345678-1234-4321-8321-123456789014"
	wrong := false
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method != "GET" || !strings.HasSuffix(r.URL.Path, "/"+root+"/asac/candidates/"+candidate) {
			t.Error("unexpected candidate request", r.Method, r.URL.Path)
		}
		resource := root
		if wrong {
			resource = candidate
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"schema_version": "1.0", "resource_id": resource, "candidate_id": candidate, "state": "ready", "published": false}})
	}))
	defer server.Close()
	for _, kind := range []string{"agent", "network"} {
		args := []string{kind, root, "candidate", candidate, "--api-url", server.URL, "--project", root, "--output", "json"}
		code, response := invoke(t, args, "")
		if code != 0 || packagefmt.Object(response["data"])["state"] != "ready" {
			t.Fatal("nested inspection output", code, response)
		}
		wrong = true
		if code, response := invoke(t, args, ""); code != 9 {
			t.Fatal("candidate owner mismatch accepted", code, response)
		}
		wrong = false
		before := requests
		if code, response := invoke(t, append(args, "--dry-run"), ""); code != 0 || requests != before {
			t.Fatal("inspection dry run performed HTTP", code, response)
		}
	}
}

func TestEmptyCandidateRevisionNeverFallsBackToLegacyStage(t *testing.T) {
	for _, kind := range []string{"agent", "network"} {
		code, response := invoke(t, []string{kind, "12345678-1234-4321-8321-123456789013", "stage", "--revision=", "--yes", "--output", "json"}, "")
		if code != 2 || !strings.Contains(packagefmt.Text(packagefmt.Object(response["error"])["message"]), "refusing legacy") {
			t.Fatal(code, response)
		}
	}
}
