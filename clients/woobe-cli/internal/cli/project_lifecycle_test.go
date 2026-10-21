package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestProjectLifecycleRequiresAdvertisedPolicyRouteBeforeWrite(t *testing.T) {
	writes := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			writes++
		}
		_, _ = w.Write([]byte(`{"paths":{}}`))
	}))
	defer server.Close()
	code, _ := invoke(t, []string{"project", "lifecycle", "update", "--project", "550e8400-e29b-41d4-a716-446655440000", "--api-url", server.URL, "--file", "-"}, `{"operation_id":"550e8400-e29b-41d4-a716-446655440001","expected_generation":0,"managed":true,"production_actors":[],"reason":"Enable lifecycle gate"}`)
	if code != 9 || writes != 0 {
		t.Fatal(code, writes)
	}
}

func TestProjectLifecycleYAMLAndOriginalOperationReadNeedNoDevelopmentConfig(t *testing.T) {
	project := "550e8400-e29b-41d4-a716-446655440000"
	operation := "550e8400-e29b-41d4-a716-446655440001"
	writes, observations := 0, 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/openapi.json" {
			_, _ = w.Write([]byte(`{"paths":{"/core/projects/{project_id}/lifecycle-policy":{"put":{"operationId":"change_policy"},"get":{"operationId":"get_policy"}},"/core/projects/{project_id}/lifecycle-policy/operations/{operation_id}":{"get":{"operationId":"policy_operation"}}}}`))
			return
		}
		if r.Method == "PUT" {
			writes++
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body["operation_id"] != operation || body["expected_generation"] != float64(0) || body["managed"] != true || body["reason"] != "Enable lifecycle gate" {
				t.Error("lost authority body", body)
			}
		} else if r.Method == "GET" && strings.HasSuffix(r.URL.Path, "/operations/"+operation) {
			observations++
		} else {
			t.Error("unexpected lifecycle request", r.Method, r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"data":{"operation_id":"` + operation + `","policy":{"generation":1,"managed":true},"write_outcome":"committed","complete":true}}`))
	}))
	defer server.Close()
	args := []string{"--api-url", server.URL, "--project", project}
	yaml := "operation_id: " + operation + "\nexpected_generation: 0\nmanaged: true\nproduction_actors: []\nreason: Enable lifecycle gate\n"
	code, _ := invoke(t, append([]string{"project", "lifecycle", "update", "--file", "-", "--input-format", "yaml"}, args...), yaml)
	if code != 0 || writes != 1 {
		t.Fatal(code, writes)
	}
	code, _ = invoke(t, append([]string{"project", "lifecycle", "operation", operation}, args...), "")
	if code != 0 || writes != 1 || observations != 1 {
		t.Fatal(code, writes, observations)
	}
}
