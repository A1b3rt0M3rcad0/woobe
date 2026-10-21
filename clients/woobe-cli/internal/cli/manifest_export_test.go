package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestManifestExportNeverClaimsApplyReady(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(`{"data":{"id":"a"}}`)) }))
	defer s.Close()
	code, v := invoke(t, []string{"manifest", "export", "--resource", "agent", "--id", "a", "--api-url", s.URL}, "")
	if code != 0 || v["data"].(map[string]any)["complete"] != false {
		t.Fatal(v)
	}
}
