package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
)

func TestPartialApplyReportsCommittedAndRejectedSteps(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if n == 1 {
			_, _ = w.Write([]byte(`{"data":{"id":"a"}}`))
			return
		}
		w.WriteHeader(403)
	}))
	defer s.Close()
	body := `{"schema_version":"1","project_id":"p","steps":[{"id":"a","command":"project agent create","body":{"name":"A"}},{"id":"b","command":"project agent prompt create","args":["${steps.a.id}"],"depends_on":["a"],"body":{"content":"Teach"}}]}`
	out := &bytes.Buffer{}
	a := New(bytes.NewBufferString(body), out, &bytes.Buffer{})
	dir := t.TempDir()
	code := a.Execute(context.Background(), []string{"manifest", "apply", "--file", "-", "--yes", "--project", "p", "--api-url", s.URL, "--config", filepath.Join(dir, "config"), "--checkpoint", filepath.Join(dir, "cp")})
	var v map[string]any
	_ = json.Unmarshal(out.Bytes(), &v)
	if code != 10 {
		t.Fatal(code, out.String())
	}
	data := v["data"].(map[string]any)
	counts := data["counts"].(map[string]any)
	if counts["committed"] != float64(1) || counts["rejected"] != float64(1) || data["checkpoint_saved"] != true {
		t.Fatal(data)
	}
}
