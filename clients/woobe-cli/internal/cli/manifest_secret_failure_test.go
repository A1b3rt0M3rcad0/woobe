package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/credentials"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func secretPlanRun(t *testing.T, args []string, body string) (int, string) {
	t.Helper()
	out := &bytes.Buffer{}
	app := New(strings.NewReader(body), out, &bytes.Buffer{})
	code := app.Execute(context.Background(), args)
	return code, out.String()
}

func TestUncertainProtectedWriteNeverReplaysAndRedactsError(t *testing.T) {
	const value = "fixture-sensitive-value"
	dir := t.TempDir()
	cp := filepath.Join(dir, "cp")
	if e := (credentials.Store{Dir: filepath.Join(dir, "credentials")}).Put("auth", value); e != nil {
		t.Fatal(e)
	}
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.WriteHeader(500)
		json.NewEncoder(w).Encode(map[string]any{"message": "failed with " + value})
	}))
	defer server.Close()
	plan := `{"schema_version":"1","project_id":"p","steps":[{"id":"s","command":"project tool create","body":{"config":{"headers":{"Authorization":{"$secret_ref":"auth"}}}}}]}`
	args := []string{"manifest", "apply", "--project", "p", "--api-url", server.URL, "--config", filepath.Join(dir, "config"), "--checkpoint", cp, "--file", "-", "--yes"}
	for i := 0; i < 2; i++ {
		code, out := secretPlanRun(t, args, plan)
		if code != 10 || strings.Contains(out, value) {
			t.Fatal(code, "unexpected failure output")
		}
	}
	if calls != 1 {
		t.Fatal("uncertain write replayed", calls)
	}
	b, e := os.ReadFile(cp)
	if e != nil || strings.Contains(string(b), value) {
		t.Fatal("checkpoint leaked", e)
	}
}

func TestProtectedDryRunAndUnavailableReferencesDoNotWrite(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls++ }))
	defer server.Close()
	plan := `{"schema_version":"1","project_id":"p","steps":[{"id":"s","command":"project tool create","body":{"api_key":{"$secret_ref":"missing"}}}]}`
	for _, mode := range []string{"dry", "missing", "skip"} {
		dir := t.TempDir()
		cp := filepath.Join(dir, "cp")
		args := []string{"manifest", "apply", "--project", "p", "--api-url", server.URL, "--config", filepath.Join(dir, "config"), "--checkpoint", cp, "--file", "-", "--yes"}
		expected := 3
		if mode == "dry" {
			args = append(args, "--dry-run")
			expected = 0
		}
		if mode == "skip" {
			args = append(args, "--skip-unchanged")
			expected = 9
		}
		code, out := secretPlanRun(t, args, plan)
		if code != expected {
			t.Fatal(mode, code, out)
		}
		if _, e := os.Stat(cp); !os.IsNotExist(e) {
			t.Fatal("checkpoint created before write", mode)
		}
	}
	if calls != 0 {
		t.Fatal(calls)
	}
}
