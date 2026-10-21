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

func TestApplyPreservesReturnedNumbersInDependencies(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if n == 1 {
			w.Write([]byte(`{"data":{"id":"a","revision":9007199254740993}}`))
			return
		}
		var v map[string]any
		d := json.NewDecoder(r.Body)
		d.UseNumber()
		if e := d.Decode(&v); e != nil {
			t.Fatal(e)
		}
		if v["revision"] != json.Number("9007199254740993") {
			t.Error(v)
		}
		w.Write([]byte(`{"data":{"id":"b"}}`))
	}))
	defer s.Close()
	body := `{"schema_version":"1","project_id":"p","steps":[{"id":"a","command":"project agent create","body":{}},{"id":"b","command":"project agent update","args":["${steps.a.id}"],"depends_on":["a"],"body":{"revision":"${steps.a.revision}"}}]}`
	dir := t.TempDir()
	out := &bytes.Buffer{}
	a := New(bytes.NewBufferString(body), out, &bytes.Buffer{})
	if code := a.Execute(context.Background(), []string{"manifest", "apply", "--file", "-", "--yes", "--api-url", s.URL, "--project", "p", "--checkpoint", filepath.Join(dir, "cp"), "--config", filepath.Join(dir, "config")}); code != 0 {
		t.Fatal(code, out.String())
	}
	b, _ := os.ReadFile(filepath.Join(dir, "cp"))
	if !bytes.Contains(b, []byte("9007199254740993")) {
		t.Fatal(string(b))
	}
}
