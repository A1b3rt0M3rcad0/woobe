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
)

func TestCaptureRoundTripWritesOnlySelectedFields(t *testing.T) {
	reads, patches := 0, 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "GET" {
			reads++
			w.Header().Set("ETag", "rev")
			_, _ = w.Write([]byte(`{"data":{"id":"a","project_id":"p","name":"A","description":null,"untouched":"keep","token":"secret"}}`))
			return
		}
		patches++
		if r.Header.Get("If-Match") != "rev" {
			t.Error("revision lost")
		}
		var b map[string]any
		_ = json.NewDecoder(r.Body).Decode(&b)
		if len(b) != 2 || b["name"] != "A" {
			t.Error(b)
		}
		if v, ok := b["description"]; !ok || v != nil {
			t.Error("null lost")
		}
		_, _ = w.Write([]byte(`{"data":{"id":"a"}}`))
	}))
	defer s.Close()
	dir := t.TempDir()
	p := filepath.Join(dir, "resource.json")
	code, v := invoke(t, []string{"manifest", "capture", "--kind", "Agent", "--id", "a", "--project", "p", "--api-url", s.URL, "--field", "name", "--field", "description", "--destination", p}, "")
	if code != 0 {
		t.Fatal(v)
	}
	raw, _ := os.ReadFile(p)
	if bytes.Contains(raw, []byte("secret")) || bytes.Contains(raw, []byte("untouched")) {
		t.Fatal(string(raw))
	}
	a := New(bytes.NewReader(raw), &bytes.Buffer{}, &bytes.Buffer{})
	if code := a.Execute(context.Background(), []string{"manifest", "apply", "--file", "-", "--api-url", s.URL, "--project", "p", "--config", filepath.Join(dir, "config"), "--checkpoint", filepath.Join(dir, "cp"), "--yes"}); code != 0 {
		t.Fatal(code)
	}
	if reads != 1 || patches != 1 {
		t.Fatal(reads, patches)
	}
}
func TestCaptureRejectsHiddenSecretOrForeignState(t *testing.T) {
	for _, tc := range []struct {
		field, body string
		code        int
	}{{"missing", `{"id":"a"}`, 5}, {"token", `{"id":"a","token":"secret"}`, 2}, {"settings", `{"id":"a","settings":{"api_key":"secret"}}`, 2}, {"name", `{"id":"other","name":"A"}`, 6}, {"name", `{"id":"a","project_id":"other","name":"A"}`, 6}} {
		s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { _ = json.NewEncoder(w).Encode(json.RawMessage(tc.body)) }))
		code, _ := invoke(t, []string{"manifest", "capture", "--kind", "Agent", "--id", "a", "--project", "p", "--api-url", s.URL, "--field", tc.field}, "")
		s.Close()
		if code != tc.code {
			t.Fatal(tc, code)
		}
	}
}
