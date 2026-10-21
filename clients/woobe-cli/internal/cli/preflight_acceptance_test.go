package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const validationPlan = `{"schema_version":"1","project_id":"p","steps":[{"id":"a","command":"project agent create","body":{"name":"A"}},{"id":"b","command":"project agent update","args":["${steps.a.id}"],"depends_on":["a"],"body":{"revision":"${steps.a.revision}"}}]}`
const validationAPI = `{"paths":{"/ai/agents":{"post":{"requestBody":{"content":{"application/json":{"schema":{"required":["name"]}}}}}},"/ai/agents/{agent_id}":{"patch":{"requestBody":{"content":{"application/json":{"schema":{"properties":{"revision":{"type":"integer"}}}}}}}}}}`

func TestManifestPreflightDeferredAndStrictEvidence(t *testing.T) {
	reads := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		reads++
		if r.Method != "GET" || r.URL.Path != "/openapi.json" {
			t.Error("mutation")
		}
		w.Write([]byte(validationAPI))
	}))
	defer s.Close()
	for _, strict := range []bool{false, true} {
		args := []string{"manifest", "preflight", "--file", "-", "--project", "p", "--api-url", s.URL}
		expected := 0
		if strict {
			args = append(args, "--require-complete")
			expected = 9
		}
		code, v := invoke(t, args, validationPlan)
		if code != expected || v["data"].(map[string]any)["complete"] != false || v["meta"].(map[string]any)["complete"] != false {
			t.Fatal(code, v)
		}
	}
	if reads != 2 {
		t.Fatal(reads)
	}
}
func TestPreflightDryRunAndSchemaPin(t *testing.T) {
	reads, writes := 0, 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" {
			reads++
			w.Write([]byte(validationAPI))
			return
		}
		writes++
		w.Write([]byte(`{"id":"a"}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"manifest", "preflight", "--file", "-", "--project", "p", "--api-url", s.URL, "--dry-run", "--require-complete"}, validationPlan)
	if code != 9 || reads != 0 {
		t.Fatal(code, v, reads)
	}
	for _, pin := range []string{strings.Repeat("0", 64), schemaDigest(schemaDoc(validationAPI))} {
		code, v = invoke(t, []string{"project", "agent", "create", "--file", "-", "--api-url", s.URL, "--validate-body", "--schema-sha256", pin}, `{"name":"A"}`)
		want := 0
		if pin == strings.Repeat("0", 64) {
			want = 6
		}
		if code != want {
			t.Fatal(code, v)
		}
	}
	if reads != 2 || writes != 1 {
		t.Fatal(reads, writes)
	}
}
func TestValidatedApplyStopsBeforeWriteAndRetainsResume(t *testing.T) {
	reads, writes := 0, 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" {
			reads++
			w.Write([]byte(validationAPI))
			return
		}
		writes++
		if writes == 1 {
			w.Write([]byte(`{"data":{"id":"a","revision":"wrong"}}`))
		} else {
			t.Error("invalid dependent mutation")
		}
	}))
	defer s.Close()
	dir := t.TempDir()
	cp := filepath.Join(dir, "cp")
	args := []string{"manifest", "apply", "--file", "-", "--project", "p", "--api-url", s.URL, "--validate-body", "--yes", "--checkpoint", cp, "--config", filepath.Join(dir, "config")}
	for i := 0; i < 2; i++ {
		out := &bytes.Buffer{}
		a := New(bytes.NewBufferString(validationPlan), out, &bytes.Buffer{})
		code := a.Execute(context.Background(), args)
		var v map[string]any
		json.Unmarshal(out.Bytes(), &v)
		if code != 10 || v["error"].(map[string]any)["write_outcome"] != "not_attempted" {
			t.Fatal(code, out.String())
		}
		if v["data"].(map[string]any)["cause"].(map[string]any)["exit_code"] != float64(2) {
			t.Fatal(v)
		}
	}
	b, _ := os.ReadFile(cp)
	saved, e := parseCheckpoint(b)
	if e != nil || saved.Steps["a"] != "committed" || saved.Steps["b"] != "not_attempted" || reads != 2 || writes != 1 {
		t.Fatal(saved, e, reads, writes)
	}
}
func TestDeferredBodyStillRequiresSupportedAdvertisedOperation(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"paths":{"/ai/agents":{"post":{"requestBody":{"content":{"application/json":{"schema":true}}}}}}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"manifest", "preflight", "--file", "-", "--project", "p", "--api-url", s.URL}, validationPlan)
	if code != 9 {
		t.Fatal(code, v)
	}
}
