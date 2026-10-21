package cli

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestDoctorPartialPreservesEvidence(t *testing.T) {
	n := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		if r.URL.Path == "/identity/users/me" {
			w.WriteHeader(401)
			return
		}
		_, _ = w.Write([]byte(`{"paths":{}}`))
	}))
	defer s.Close()
	code, v := invoke(t, []string{"doctor", "--api-url", s.URL}, "")
	if code != 10 || n != 3 || v["success"] != false || v["data"] == nil {
		t.Fatal(code, v, n)
	}
}
