package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

func TestSemanticStateDiffPreservesMissingNullAndPrecision(t *testing.T) {
	changes, err := fieldChanges(map[string]any{"same": json.Number("1e0"), "precise": json.Number("9007199254740992"), "null": nil}, map[string]any{"same": json.Number("1.0"), "precise": json.Number("9007199254740993"), "null": nil, "missing": nil})
	if err != nil || len(changes) != 2 || changes[0].Field != "missing" || changes[0].Present || changes[1].Field != "precise" {
		t.Fatal(changes, err)
	}
	_, err = fieldChanges(map[string]any{"x": json.Number("1e9999")}, map[string]any{"x": nil})
	if err == nil || output.Normalize(err).Code != 9 {
		t.Fatal(err)
	}
}

func TestSemanticNumericApplySkipsWriteAndRetainsCheckpoint(t *testing.T) {
	reads, writes := 0, 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			writes++
			t.Error("unexpected write")
			w.WriteHeader(500)
			return
		}
		reads++
		_, _ = w.Write([]byte(`{"data":{"id":"a","settings":{"temperature":1e0,"limits":[9007199254740993.0]}}}`))
	}))
	defer s.Close()
	dir := t.TempDir()
	cp := filepath.Join(dir, "checkpoint")
	body := `{"schema_version":"2","project_id":"p","resources":[{"key":"a","kind":"Agent","action":"update","resource_id":"a","spec":{"settings":{"temperature":1.0,"limits":[9007199254740993]}}}]}`
	args := []string{"manifest", "apply", "--file", "-", "--api-url", s.URL, "--project", "p", "--config", filepath.Join(dir, "config"), "--checkpoint", cp, "--yes", "--skip-unchanged"}
	for i := 0; i < 2; i++ {
		out := &bytes.Buffer{}
		a := New(bytes.NewBufferString(body), out, &bytes.Buffer{})
		if code := a.Execute(context.Background(), args); code != 0 {
			t.Fatal(code, out.String())
		}
	}
	b, err := os.ReadFile(cp)
	if err != nil {
		t.Fatal(err)
	}
	c, err := parseCheckpoint(b)
	if err != nil || c.Steps["a"] != "unchanged" || reads != 1 || writes != 0 {
		t.Fatal(c, err, reads, writes)
	}
}

func TestResourceDiffRequiresExpectedRevisionEvidence(t *testing.T) {
	for _, tc := range []struct {
		etag string
		code int
	}{{"", 9}, {"other", 6}, {"rev", 0}} {
		s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.Method != "GET" {
				t.Error("write attempted")
			}
			w.Header().Set("ETag", tc.etag)
			_, _ = w.Write([]byte(`{"data":{"id":"a","name":"A"}}`))
		}))
		code, v := invoke(t, []string{"manifest", "diff", "--file", "-", "--project", "p", "--api-url", s.URL}, `{"schema_version":"2","project_id":"p","resources":[{"key":"a","kind":"Agent","action":"update","resource_id":"a","spec":{"name":"A"},"if_match":"rev"}]}`)
		s.Close()
		if code != tc.code {
			t.Fatal(tc, code, v)
		}
	}
}
