package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestRuntimeInputPreservesSessionAndPreciseExternalMetadata(t *testing.T) {
	for _, raw := range []string{
		`{"input":"Hello","session_id":"existing-session","options":{"metadata":{"counter":9007199254740993}}}`,
		`{"input":"Hello","options":{"session_id":"existing-session","metadata":{"counter":9007199254740993}}}`,
		`{"input":"Hello","options":{"SessionID":"existing-session","Metadata":{"counter":9007199254740993}}}`,
	} {
		input, err := decodeRuntimeInput([]byte(raw))
		if err != nil || input.Options.SessionID != "existing-session" || input.Options.Metadata["counter"].(json.Number).String() != "9007199254740993" {
			t.Fatal(input, err)
		}
	}
	for _, raw := range []string{
		`{"input":"Hello","session":"ignored-typo"}`,
		`{"input":"Hello","session_id":null}`,
		`{"input":"Hello","options":{"session":"ignored-typo"}}`,
		`{"input":"Hello","options":{"session_id":"one","SessionID":"two"}}`,
		`{"input":"Hello","session_id":"one","options":{"session_id":"two"}}`,
	} {
		if _, err := decodeRuntimeInput([]byte(raw)); err == nil {
			t.Fatal("unsafe input accepted", raw)
		}
	}
}
func TestRuntimeTargetForwardsYamlSessionIdentityForAgentAndNetwork(t *testing.T) {
	t.Setenv("WOOBE_RUNTIME_KEY", "dummy-test-only-runtime-key")
	for _, kind := range []string{"agent", "network"} {
		calls := 0
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			calls++
			if r.URL.Path != "/v1/run" {
				t.Errorf("unexpected runtime path: %s", r.URL.Path)
			}
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Error(err)
			}
			if body["session_id"] != "existing-session" {
				t.Errorf("session identity dropped: %v", body["session_id"])
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"answer": "ok", "session_id": "existing-session"}})
		}))
		code, response := invoke(t, []string{"runtime", "target", "run", "alias", "--target-kind", kind, "--api-url", server.URL, "--file", "-", "--yes", "--output", "json"}, "input: Hello\nsession_id: existing-session\n")
		server.Close()
		if code != 0 || calls != 1 || !strings.Contains(response["data"].(map[string]any)["data"].(map[string]any)["session_id"].(string), "existing-session") {
			t.Fatal(kind, code, calls, response)
		}
	}
}

func TestRuntimeResponsePreservesExactAdmissionGeneration(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"success":true,"data":{"runtime_identity":{"selection_generation":9007199254740993}}}`))
	}))
	defer server.Close()
	capture := &runtimeResponseCapture{base: http.DefaultTransport}
	client := &http.Client{Transport: capture}
	response, err := client.Post(server.URL+"/v1/run", "application/json", strings.NewReader(`{}`))
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	result, err := capture.preciseResult(nil)
	if err != nil || result.Data["runtime_identity"].(map[string]any)["selection_generation"].(json.Number).String() != "9007199254740993" {
		t.Fatal(result, err)
	}
}
