package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestAdvertisedCategoryRouteUsesServerAuthority(t *testing.T) {
	writes := 0
	reads := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/openapi.json" {
			reads++
			_, _ = w.Write([]byte(`{"paths":{"/identity/workspaces/{workspace_id}/authority-categories":{"post":{"operationId":"create_category"}}}}`))
			return
		}
		if r.URL.Path != "/identity/workspaces/w/authority-categories" {
			t.Error(r.URL.Path)
		}
		writes++
		w.WriteHeader(403)
	}))
	defer s.Close()
	code, _ := invoke(t, []string{"workspace", "authority", "category", "create", "--workspace", "w", "--api-url", s.URL, "--file", "-"}, `{"name":"reader","permissions":["agent:read"]}`)
	if code != 4 || reads != 1 || writes != 1 {
		t.Fatal(code, reads, writes)
	}
}
func TestMissingCategoryCapabilityDoesNotWrite(t *testing.T) {
	writes := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			writes++
		}
		_, _ = w.Write([]byte(`{"paths":{}}`))
	}))
	defer s.Close()
	code, _ := invoke(t, []string{"workspace", "authority", "category", "create", "--workspace", "w", "--api-url", s.URL, "--file", "-"}, `{}`)
	if code != 9 || writes != 0 {
		t.Fatal(code, writes)
	}
}
