package cli

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSkipUnchangedRequiresObservedExpectedRevision(t *testing.T) {
	for _, tc := range []struct {
		etag string
		code int
	}{{"", 9}, {"other", 6}, {"expected", 0}} {
		s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.Method != "GET" {
				t.Error("write attempted")
			}
			w.Header().Set("ETag", tc.etag)
			_, _ = w.Write([]byte(`{"data":{"id":"a","name":"A"}}`))
		}))
		a := New(nil, nil, nil)
		a.APIURL = s.URL
		a.ConfigPath = t.TempDir() + "/config"
		_, unchanged, e := a.observeUnchanged(context.Background(), manifest.Step{Command: "project agent update", Args: []string{"a"}, Body: []byte(`{"name":"A"}`), IfMatch: "expected"})
		if e != nil {
			if output.Normalize(e).Code != tc.code {
				t.Fatal(e)
			}
		} else if tc.code != 0 || !unchanged {
			t.Fatal(tc, unchanged)
		}
		s.Close()
	}
}
func TestSkipUnchangedDetectsChangedFieldsAndUnsupportedReaders(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"data":{"id":"a","name":"old"}}`))
	}))
	defer s.Close()
	a := New(nil, nil, nil)
	a.APIURL = s.URL
	a.ConfigPath = t.TempDir() + "/config"
	_, unchanged, e := a.observeUnchanged(context.Background(), manifest.Step{Command: "project agent update", Args: []string{"a"}, Body: []byte(`{"name":"new"}`)})
	if e != nil || unchanged {
		t.Fatal(e, unchanged)
	}
	_, _, e = a.observeUnchanged(context.Background(), manifest.Step{Command: "project network draft update", Args: []string{"n"}, Body: []byte(`{}`)})
	if e == nil || output.Normalize(e).Code != 9 {
		t.Fatal(e)
	}
}
