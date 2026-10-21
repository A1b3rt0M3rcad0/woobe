package cli

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func TestManifestParameterValidationStopsBeforeWrite(t *testing.T) {
	writes := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/openapi.json" {
			w.Write([]byte(`{"openapi":"3.1.0","paths":{"/ai/agents/{agent_id}":{"patch":{"parameters":[{"name":"agent_id","in":"path","required":true,"schema":{"type":"string","format":"uuid"}}]}}}}`))
			return
		}
		writes++
		w.Write([]byte(`{"id":"x"}`))
	}))
	defer s.Close()
	cp := filepath.Join(t.TempDir(), "cp.json")
	code, v := invoke(t, []string{"manifest", "apply", "--yes", "--checkpoint", cp, "--file", "-", "--api-url", s.URL, "--validate-parameters"}, `{"schema_version":"1","steps":[{"id":"a","command":"project agent update","args":["invalid"],"body":{"name":"A"}}]}`)
	if code != 10 || writes != 0 {
		t.Fatal(code, v, writes)
	}
	code, v = invoke(t, []string{"manifest", "status", "--checkpoint", cp}, "")
	if code != 0 {
		t.Fatal(code, v)
	}
	data := v["data"].(map[string]any)
	if data["checkpoint"].(map[string]any)["steps"].(map[string]any)["a"] != "not_attempted" {
		t.Fatal(v)
	}
}

func TestManifestPreflightIncludesParameterEvidence(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/openapi.json" {
			t.Error("write attempted")
		}
		w.Write([]byte(`{"openapi":"3.1.0","paths":{"/ai/agents/{agent_id}":{"patch":{"parameters":[{"name":"agent_id","in":"path","required":true,"schema":{"type":"string","format":"uuid"}}],"requestBody":{"content":{"application/json":{"schema":{"type":"object"}}}}}}}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"manifest", "preflight", "--file", "-", "--api-url", s.URL, "--validate-parameters"}, `{"schema_version":"1","steps":[{"id":"a","command":"project agent update","args":["550e8400-e29b-41d4-a716-446655440000"],"body":{"name":"A"}}]}`)
	if code != 0 {
		t.Fatal(code, v)
	}
	row := v["data"].(map[string]any)["operations"].([]any)[0].(map[string]any)
	if row["path_query_validation"] != "supported_schema_subset" || row["write_executed"] != false {
		t.Fatal(v)
	}
}

func TestParameterPreflightFailureDoesNotClaimBodyEvaluation(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"paths":{"/ai/agents/{agent_id}":{"patch":{"parameters":[{"name":"agent_id","in":"path","required":true,"schema":{"type":"string","format":"uuid"}}]}}}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"manifest", "preflight", "--file", "-", "--api-url", s.URL, "--validate-parameters"}, `{"schema_version":"1","steps":[{"id":"a","command":"project agent update","args":["invalid"],"body":{"name":"A"}}]}`)
	if code != 2 {
		t.Fatal(code, v)
	}
	row := v["data"].(map[string]any)["operations"].([]any)[0].(map[string]any)
	if row["body_validation"] != "not_evaluated" || row["path_query_validation"] != "failed" {
		t.Fatal(v)
	}
}
