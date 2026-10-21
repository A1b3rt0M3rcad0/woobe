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

func TestRuntimeInputAcceptsExactMultimodalArtifactReferences(t *testing.T) {
	raw := []byte(`{"content_parts":[{"type":"text","text":"Summarize this"},{"type":"artifact","ref":{"artifact_id":"artifact-1","revision_id":"revision-2"},"media_type_hint":"application/pdf"}],"session_id":"existing-session","options":{"external_context":{"workspace":"team-docs"}}}`)
	input, err := decodeRuntimeInput(raw)
	if err != nil {
		t.Fatal(err)
	}
	if input.Input != "" || input.Options.SessionID != "existing-session" || len(input.ContentParts) != 2 || input.ContentParts[1].Ref == nil {
		t.Fatalf("multimodal input was not preserved: %+v", input)
	}
	if input.ContentParts[1].Ref.ArtifactID != "artifact-1" || input.ContentParts[1].Ref.RevisionID != "revision-2" || input.Options.ExternalContext["workspace"] != "team-docs" {
		t.Fatalf("exact reference or external context changed: %+v", input)
	}
	legacy, err := decodeRuntimeInput([]byte(`{"input":"legacy message"}`))
	if err != nil || legacy.Input != "legacy message" || legacy.ContentParts != nil {
		t.Fatalf("legacy text behavior changed: %+v %v", legacy, err)
	}
}

func TestRuntimeInputRejectsAmbiguousOrMalformedContentParts(t *testing.T) {
	for _, raw := range []string{
		`{"content_part":[{"type":"text","text":"typo"}]}`,
		`{"content_parts":[{"type":"text","text":"x","extra":true}]}`,
		`{"content_parts":[{"type":"artifact","ref":{"artifact_id":"a","revision_id":"r","workspace_id":"private"}}]}`,
		`{"content_parts":[{"type":"artifact","ref":{"artifact_id":"a"}}]}`,
		`{"content_parts":[{"type":"text","text":"x","ref":null}]}`,
		`{"content_parts":[{"type":"artifact","ref":{"artifact_id":"a","revision_id":"r"},"text":""}]}`,
		`{"content_parts":[{"type":"image","url":"https://private.invalid/signed"}]}`,
		`{"input":"legacy","content_parts":[{"type":"text","text":"also"}]}`,
		`{"content_parts":[],"input":""}`,
		`{"content_parts":[{"type":"text","text":"x"}],"input":null}`,
		`{"content_parts":[{"type":"text","text":"x"}],"input":" "}`,
		`{"content_parts":[{"type":"text","text":"x"}],"options":{"metadata":{"x":1,"x":2}}}`,
		`{"input":"x","input":"y"}`,
	} {
		if _, err := decodeRuntimeInput([]byte(raw)); err == nil {
			t.Fatalf("ambiguous or malformed input accepted: %s", raw)
		}
	}
}

func TestRuntimeMultimodalRequestIsNotFlattenedForOlderServer(t *testing.T) {
	t.Setenv("WOOBE_RUNTIME_KEY", "dummy-test-only-runtime-key")
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Error(err)
		}
		if body["message"] != "" || body["content_parts"] == nil {
			t.Errorf("multimodal input was silently flattened: %#v", body)
		}
		w.WriteHeader(http.StatusUnprocessableEntity)
		_, _ = w.Write([]byte(`{"detail":"content_parts unsupported"}`))
	}))
	defer server.Close()
	input := `content_parts:
  - type: artifact
    ref:
      artifact_id: artifact-1
      revision_id: revision-2
`
	code, _ := invoke(t, []string{"runtime", "target", "run", "alias", "--target-kind", "agent", "--api-url", server.URL, "--file", "-", "--yes"}, input)
	if code != 2 || calls != 1 {
		t.Fatalf("older server rejection did not remain explicit: code=%d calls=%d", code, calls)
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

func TestRuntimeTargetForwardsArtifactYamlForAgentAndNetwork(t *testing.T) {
	t.Setenv("WOOBE_RUNTIME_KEY", "dummy-test-only-runtime-key")
	for _, kind := range []string{"agent", "network"} {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path != "/v1/run" {
				t.Errorf("unexpected runtime path: %s", r.URL.Path)
			}
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Error(err)
			}
			parts, ok := body["content_parts"].([]any)
			if !ok || body["message"] != "" || body["session_id"] != "existing-session" || body["external_context"].(map[string]any)["workspace"] != "team-docs" {
				t.Errorf("multimodal runtime contract changed: %#v", body)
			}
			artifact := parts[1].(map[string]any)["ref"].(map[string]any)
			if artifact["artifact_id"] != "artifact-1" || artifact["revision_id"] != "revision-2" {
				t.Errorf("exact Artifact revision was not forwarded: %#v", artifact)
			}
			_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"answer": "ok", "session_id": "existing-session"}})
		}))
		input := "content_parts:\n  - type: text\n    text: Summarize this\n  - type: artifact\n    ref:\n      artifact_id: artifact-1\n      revision_id: revision-2\n    media_type_hint: application/pdf\nsession_id: existing-session\noptions:\n  external_context:\n    workspace: team-docs\n"
		code, _ := invoke(t, []string{"runtime", "target", "run", "alias", "--target-kind", kind, "--api-url", server.URL, "--file", "-", "--yes", "--output", "json"}, input)
		server.Close()
		if code != 0 {
			t.Fatalf("%s multimodal run failed with code %d", kind, code)
		}
	}
}

func TestRuntimeContentPartsDryRunAndLocalValidationDoNotContactServer(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls++ }))
	defer server.Close()
	valid := `content_parts:
  - type: artifact
    ref:
      artifact_id: artifact-1
      revision_id: revision-2
`
	for _, args := range [][]string{
		{"runtime", "target", "run", "alias", "--api-url", server.URL, "--file", "-", "--dry-run", "--output", "json"},
		{"validate-input", "--command", "runtime target run", "--api-url", server.URL, "--file", "-", "--output", "json"},
	} {
		code, result := invoke(t, args, valid)
		if code != 0 || result["data"].(map[string]any)["executed"] != false {
			t.Fatalf("local multimodal validation failed: %d %#v", code, result)
		}
	}
	code, _ := invoke(t, []string{"validate-input", "--command", "runtime target run", "--api-url", server.URL, "--file", "-"}, `content_part: []`)
	if code != 2 || calls != 0 {
		t.Fatalf("bad local input was not refused offline: code=%d calls=%d", code, calls)
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
