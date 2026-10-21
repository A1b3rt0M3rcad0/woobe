package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestSecretIssuanceRejectionLeavesNoDestinationOrTemporaryFile(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(403); w.Write([]byte(`{"success":false}`)) }))
	defer server.Close()
	folder := t.TempDir()
	destination := filepath.Join(folder, "secret.json")
	code, result := invoke(t, []string{"project", "api-key", "create", "--api-url", server.URL, "--project", "p", "--file", "-", "--secret-file", destination}, `{}`)
	if code != 4 {
		t.Fatal(code, result["error"])
	}
	entries, err := os.ReadDir(folder)
	if err != nil || len(entries) != 0 {
		t.Fatal("Rejected issuance left a file", entries, err)
	}
}
func TestSecretIssuancePublishesVersionedPrivateEnvelopeAndImportsCredential(t *testing.T) {
	const secret = "private-issued-credential"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"success":true,"data":{"key":"` + secret + `","id":"issued"}}`))
	}))
	defer server.Close()
	destination := filepath.Join(t.TempDir(), "secret.json")
	code, result := invoke(t, []string{"project", "api-key", "create", "--api-url", server.URL, "--project", "p", "--file", "-", "--secret-file", destination}, `{}`)
	if code != 0 {
		t.Fatal("Issuance failed", code, result["error"])
	}
	if strings.Contains(strings.ReplaceAll(fmtJSON(result), "[REDACTED]", ""), secret) {
		t.Fatal("Issuance leaked")
	}
	data, err := packagecheckpoint.ReadPrivate(destination)
	if err != nil {
		t.Fatal(err)
	}
	var document map[string]any
	if json.Unmarshal(data, &document) != nil || document["format"] != "woobe-issued-secret" || document["file_schema_version"] != "1" {
		t.Fatal("unversioned custody")
	}
	token, err := credentialFromInput(data)
	if err != nil || token != secret {
		t.Fatal("Envelope cannot be imported")
	}
}
func fmtJSON(v any) string { b, _ := json.Marshal(v); return string(b) }
func TestCredentialImportRejectsInvalidEmptyRedactedAndAmbiguousEnvelopes(t *testing.T) {
	for _, input := range []string{"", "   ", `{}`, `{"data":{"key":"[REDACTED]"}}`, `{"format":"woobe-issued-secret","file_schema_version":"2","key":"secret"}`, `{"data":{"key":"one","token":"two"}}`, `{"success":false,"data":{"key":"secret"}}`, `[]`, `{"data":{"key":"one","key":"two"}}`, "two\nlines"} {
		if _, err := credentialFromInput([]byte(input)); err == nil {
			t.Fatal("Accepted invalid credential input", input)
		}
	}
	for _, input := range []string{"raw-token", `{"success":true,"data":{"key":"raw-token"}}`} {
		value, err := credentialFromInput([]byte(input))
		if err != nil || value != "raw-token" {
			t.Fatal("Backward compatibility broken")
		}
	}
}
func TestTimedOutReleaseTestHasDurableIdentityAndNeverReplaysExecution(t *testing.T) {
	var calls atomic.Int32
	executed := make(chan string, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if serveReleaseTestSchema(w, r) {
			return
		}
		calls.Add(1)
		var body map[string]any
		json.NewDecoder(r.Body).Decode(&body)
		id, _ := body["test_id"].(string)
		time.Sleep(240 * time.Millisecond)
		executed <- id
		w.Write([]byte(`{"success":true,"data":{"status":"passed"}}`))
	}))
	defer server.Close()
	folder := t.TempDir()
	out := &bytes.Buffer{}
	app := New(strings.NewReader(`{"project_id":"p","agent_id":"00000000-0000-4000-8000-000000000001","release_id":"00000000-0000-4000-8000-000000000002","message":"message"}`), out, &bytes.Buffer{})
	code := app.Execute(context.Background(), []string{"project", "agent", "release", "run-test", "00000000-0000-4000-8000-000000000001", "--api-url", server.URL, "--project", "p", "--file", "-", "--timeout", "80ms", "--yes", "--config", filepath.Join(folder, "config.json"), "--output", "json"})
	if code != 8 {
		t.Fatal(code, out.String())
	}
	var result map[string]any
	if json.Unmarshal(out.Bytes(), &result) != nil {
		t.Fatal(out.String())
	}
	failure := result["error"].(map[string]any)
	id := failure["test_id"].(string)
	if !uuidReference(id) || failure["write_outcome"] != "unknown" || !strings.Contains(failure["recovery_command"].(string), "release tests") {
		t.Fatal("Lost recoverable identity", result)
	}
	receipt, err := packagecheckpoint.ReadPrivate(filepath.Join(folder, "release-test-intents", id+".json"))
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(receipt, []byte(`"message"`)) {
		t.Fatal("Test input stored in operational receipt")
	}
	select {
	case actual := <-executed:
		if actual != id {
			t.Fatal("Remote test identity differs")
		}
	case <-time.After(3 * time.Second):
		t.Fatal("Remote execution did not complete")
	}
	if calls.Load() != 1 {
		t.Fatal("Unknown outcome retried POST", calls.Load())
	}
}

func TestCanonicalRunTestRejectsFailedValidationWithResultAndExitSix(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if serveReleaseTestSchema(w, r) {
			return
		}
		w.Write([]byte(`{"success":true,"data":{"id":"test","status":"failed","validation_errors":[{"code":"OUTPUT_VALIDATION_FAILED"}]}}`))
	}))
	defer server.Close()
	code, result := invoke(t, []string{"project", "agent", "release", "run-test", "00000000-0000-4000-8000-000000000001", "--api-url", server.URL, "--project", "p", "--file", "-", "--yes"}, `{"agent_id":"00000000-0000-4000-8000-000000000001","release_id":"00000000-0000-4000-8000-000000000002","message":"test"}`)
	if code != 6 || result["data"].(map[string]any)["status"] != "failed" {
		t.Fatal("Failed execution reported as successful or lost evidence", code, result)
	}
}

func serveReleaseTestSchema(w http.ResponseWriter, r *http.Request) bool {
	if r.Method != "GET" || r.URL.Path != "/openapi.json" {
		return false
	}
	w.Write([]byte(`{"openapi":"3.1.0","paths":{"/ai/agents/{agent_id}/release-tests/run":{"post":{"requestBody":{"content":{"application/json":{"schema":{"type":"object","properties":{"test_id":{"type":"string"}}}}}}}}}}`))
	return true
}
func TestReleaseTestRefusesLegacyBackendBeforeIssuingAnUnrecoverableWrite(t *testing.T) {
	var posts atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" {
			posts.Add(1)
		}
		w.Write([]byte(`{"openapi":"3.1.0","paths":{"/ai/agents/{agent_id}/release-tests/run":{"post":{"requestBody":{"content":{"application/json":{"schema":{"type":"object","properties":{}}}}}}}}}`))
	}))
	defer server.Close()
	code, _ := invoke(t, []string{"project", "agent", "release", "run-test", "00000000-0000-4000-8000-000000000001", "--api-url", server.URL, "--project", "p", "--file", "-", "--yes"}, `{"message":"test"}`)
	if code != 9 || posts.Load() != 0 {
		t.Fatal("Legacy server received an unsafe execution", code, posts.Load())
	}
}

func TestReleaseTestRefusesUnsafeRecoveryIdentifiersBeforeExecution(t *testing.T) {
	var posts atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if serveReleaseTestSchema(w, r) {
			return
		}
		posts.Add(1)
	}))
	defer server.Close()
	code, _ := invoke(t, []string{"project", "agent", "release", "run-test", "00000000-0000-4000-8000-000000000001", "--api-url", server.URL, "--project", "p", "--file", "-", "--yes"}, `{"agent_id":"$(untrusted)","release_id":"id","message":"test"}`)
	if code != 2 || posts.Load() != 0 {
		t.Fatal("Unsafe recovery identifier was accepted", code, posts.Load())
	}
}

func TestReleaseTestPreservesLargeExpectedIntegersBeforeAddingIdentity(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if serveReleaseTestSchema(w, r) {
			return
		}
		decoder := json.NewDecoder(r.Body)
		decoder.UseNumber()
		var body map[string]any
		decoder.Decode(&body)
		if body["expected_output"].(map[string]any)["value"].(json.Number).String() != "9007199254740993" {
			t.Error("Expected output was rounded")
		}
		w.Write([]byte(`{"success":true,"data":{"status":"passed"}}`))
	}))
	defer server.Close()
	code, _ := invoke(t, []string{"project", "agent", "release", "run-test", "id", "--api-url", server.URL, "--project", "p", "--file", "-", "--yes"}, `{"agent_id":"id","release_id":"release","message":"test","expected_output":{"value":9007199254740993}}`)
	if code != 0 {
		t.Fatal(code)
	}
}
