package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/credentials"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestProtectedManifestApplyResumeAndRotation(t *testing.T) {
	const secret = "fixture-provider-secret"
	dir := t.TempDir()
	config := filepath.Join(dir, "config")
	cp := filepath.Join(dir, "cp")
	store := credentials.Store{Dir: filepath.Join(dir, "credentials")}
	if e := store.Put("provider", secret); e != nil {
		t.Fatal(e)
	}
	writes := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.URL.Path != "/ai/credentials" {
			t.Error(r.Method, r.URL.Path)
		}
		writes++
		b, _ := io.ReadAll(r.Body)
		var body map[string]any
		json.Unmarshal(b, &body)
		if body["api_key"] != secret {
			t.Fatal("reference was not resolved")
		}
		json.NewEncoder(w).Encode(map[string]any{"data": map[string]any{"id": "created", "echo": "echo " + secret}})
	}))
	defer server.Close()
	plan := `{"schema_version":"1","project_id":"p","steps":[{"id":"provider","command":"project provider-credential create","body":{"api_key":{"$secret_ref":"provider"}}}]}`
	args := []string{"manifest", "apply", "--project", "p", "--api-url", server.URL, "--config", config, "--checkpoint", cp, "--file", "-", "--yes"}
	run := func() (int, map[string]any) {
		out := &bytes.Buffer{}
		app := New(strings.NewReader(plan), out, &bytes.Buffer{})
		code := app.Execute(context.Background(), args)
		var value map[string]any
		if json.Unmarshal(out.Bytes(), &value) != nil {
			t.Fatal(out.String())
		}
		return code, value
	}
	for i := 0; i < 2; i++ {
		code, v := run()
		if code != 0 {
			t.Fatal(code, v)
		}
		b, _ := json.Marshal(v)
		if strings.Contains(string(b), secret) {
			t.Fatal("output leaked credential")
		}
	}
	if writes != 1 {
		t.Fatal(writes)
	}
	b, e := os.ReadFile(cp)
	if e != nil || strings.Contains(string(b), secret) || !strings.Contains(string(b), "secret_fingerprints") {
		t.Fatal("checkpoint leaked or lacks binding", e)
	}
	if e := store.Put("provider", "rotated-fixture-secret"); e != nil {
		t.Fatal(e)
	}
	code, _ := run()
	if code != 6 || writes != 1 {
		t.Fatal(code, writes)
	}
}
