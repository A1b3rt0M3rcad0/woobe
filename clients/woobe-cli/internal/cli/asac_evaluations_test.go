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
)

func TestCandidateEvaluationLostAcceptanceReconcilesWithoutExecution(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	const candidate = "12345678-1234-4321-8321-123456789014"
	const evaluation = "12345678-1234-4321-8321-123456789015"
	const native = "01a0a033-5820-770c-854b-902864857273"
	var resource devworkspace.Resource
	var receipt map[string]any
	writes := 0
	mismatch := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var data any
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data = map[string]any{"asac": map[string]any{"schema_version": "1.0", "candidate_evaluation": true}}
		case r.Method == "GET" && strings.HasSuffix(r.URL.Path, "/candidates/"+candidate):
			data = map[string]any{"resource_id": native, "resource_uid": resource.UID, "candidate_id": candidate, "state": "ready", "record_digest": "record", "runtime_digest": "runtime"}
		case r.Method == "POST" && strings.HasSuffix(r.URL.Path, "/evaluations"):
			writes++
			var body map[string]any
			decoder := json.NewDecoder(r.Body)
			decoder.UseNumber()
			_ = decoder.Decode(&body)
			cases := body["suite"].(map[string]any)["cases"].([]any)
			number := cases[0].(map[string]any)["expected_output"].(map[string]any)["balance"]
			if number != json.Number("9007199254740993") {
				t.Error("Evaluation changed exact YAML integer", number)
			}
			if len(body) != 2 || body["suite"] == nil {
				t.Error("Evaluation sent unrecognized authority fields", body)
			}
			receipt = map[string]any{"schema_version": "1.0", "operation_id": body["operation_id"], "resource_id": native, "candidate_id": candidate, "evaluation_id": evaluation, "record_digest": "record", "runtime_digest": "runtime", "write_outcome": "committed", "state": "accepted", "published": false, "production_changed": false}
			w.WriteHeader(500)
			_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "response lost"})
			return
		case strings.Contains(r.URL.Path, "/operations/"):
			result := map[string]any{}
			for key, value := range receipt {
				result[key] = value
			}
			if mismatch {
				result["runtime_digest"] = "other"
			}
			data = map[string]any{"operation_id": receipt["operation_id"], "state": "committed", "result": result}
		case r.Method == "GET" && strings.HasSuffix(r.URL.Path, "/evaluations/"+evaluation):
			data = map[string]any{"schema_version": "1.0", "evaluation_id": evaluation, "candidate_id": candidate, "resource_id": native, "state": "running"}
		default:
			t.Error("Reconciliation executed or changed an environment", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	c, state, resource := asacWorkspace(t, server.URL)
	suite := filepath.Join(t.TempDir(), "suite.yaml")
	if err := os.WriteFile(suite, []byte("schema_version: '1.0'\nsuite_id: support\nsuite_version: '1'\ndataset_version: '1'\ncases:\n  - id: question\n    message: hello\n    expected_output:\n      balance: 9007199254740993\n"), 0600); err != nil {
		t.Fatal(err)
	}
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	execute := append([]string{"agent", "@support", "test", "--candidate", candidate, "--file", suite, "--yes"}, flags...)
	if code, value := invoke(t, execute, ""); code == 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	if code, value := invoke(t, execute, ""); code != 9 || writes != 1 {
		t.Fatal("unknown evaluation repeated", code, value, writes)
	}
	reconcile := append([]string{"agent", "@support", "draft", "reconcile"}, flags...)
	mismatch = true
	if code, value := invoke(t, reconcile, ""); code != 9 {
		t.Fatal("unrelated proof cleared pending", code, value)
	}
	mismatch = false
	if code, value := invoke(t, reconcile, ""); code != 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
	raw, err := c.ReadOperationalFile(asacPrivatePath(c, state, resource.UID, "evaluation"), 1<<20)
	if err != nil || !strings.Contains(string(raw), evaluation) {
		t.Fatal("Lost original evaluation identity", err)
	}
	if code, value := invoke(t, append([]string{"agent", native, "evaluation", evaluation}, flags...), ""); code != 0 || writes != 1 {
		t.Fatal(code, value, writes)
	}
}

func TestEvaluationInspectionScopeAndNoConfig(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	const native = "12345678-1234-4321-8321-123456789013"
	const evaluation = "12345678-1234-4321-8321-123456789015"
	requests := 0
	wrong := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		id := native
		if wrong {
			id = evaluation
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"schema_version": "1.0", "resource_id": id, "evaluation_id": evaluation, "state": "running"}})
	}))
	defer server.Close()
	for _, kind := range []string{"agent", "network"} {
		flags := []string{"--api-url", server.URL, "--project", "project", "--workspace", "workspace", "--no-project-config", "--output", "json"}
		args := append([]string{kind, native, "evaluation", evaluation}, flags...)
		if code, value := invoke(t, append(args, "--dry-run"), ""); code != 0 {
			t.Fatal(code, value)
		}
		if code, value := invoke(t, args, ""); code != 0 {
			t.Fatal(code, value)
		}
		wrong = true
		if code, value := invoke(t, args, ""); code != 9 {
			t.Fatal("Wrong owner evidence accepted", code, value)
		}
		wrong = false
	}
	if requests != 4 {
		t.Fatal("dry-run contacted backend", requests)
	}
}

func TestCandidateEvaluationRejectsAmbiguousEnvironment(t *testing.T) {
	for _, flags := range [][]string{{"--env", "draft"}, {"--version", "1.0"}} {
		args := append([]string{"agent", "id", "test", "--candidate", "12345678-1234-4321-8321-123456789014"}, flags...)
		if code, value := invoke(t, args, ""); code != 2 {
			t.Fatal(code, value)
		}
	}
	if code, value := invoke(t, []string{"network", "id", "test", "--candidate", ""}, ""); code != 2 {
		t.Fatal(code, value)
	}
}
