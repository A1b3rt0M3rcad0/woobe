package controlplane

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestTransportContract(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer fixture" {
			t.Error("missing bearer")
		}
		if r.URL.Query().Get("project_id") != "p" {
			t.Error("missing project")
		}
		if r.Header.Get("If-Match") != "rev1" {
			t.Error("missing condition")
		}
		var m map[string]any
		_ = json.NewDecoder(r.Body).Decode(&m)
		if v, ok := m["prompt"]; !ok || v != nil {
			t.Error("null lost")
		}
		if _, ok := m["name"]; ok {
			t.Error("omitted field sent")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":{"id":"a"}}`))
	}))
	defer s.Close()
	c, _ := New(s.URL, "fixture", time.Second)
	c.Headers.Set("If-Match", "rev1")
	_, _, e := c.Request(context.Background(), "PATCH", "/ai/agents/a", url.Values{"project_id": {"p"}}, []byte(`{"prompt":null}`))
	if e != nil {
		t.Fatal(e)
	}
}
func TestStatusCodes(t *testing.T) {
	for status, code := range map[int]int{401: 3, 403: 4, 404: 5, 409: 6, 412: 6, 422: 2, 501: 9} {
		status, code := status, code
		t.Run(http.StatusText(status), func(t *testing.T) {
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("X-Request-ID", "req")
				w.WriteHeader(status)
				_, _ = w.Write([]byte(`{"secret":"must-not-leak"}`))
			}))
			defer s.Close()
			c, _ := New(s.URL, "", time.Second)
			_, _, e := c.Request(context.Background(), "POST", "/x", nil, nil)
			v := output.Normalize(e)
			if v.Code != code || v.RequestID != "req" || v.Message == "must-not-leak" {
				t.Fatalf("%+v", v)
			}
		})
	}
}
func TestNoRedirectOrWriteRetry(t *testing.T) {
	count := 0
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		count++
		w.Header().Set("Location", "https://example.invalid")
		w.WriteHeader(307)
	}))
	defer s.Close()
	c, _ := New(s.URL, "fixture", time.Second)
	_, _, e := c.Request(context.Background(), "POST", "/x", nil, nil)
	if e == nil || count != 1 {
		t.Fatal("redirect or write replay")
	}
}
func TestRejectForeignPaths(t *testing.T) {
	c, _ := New("https://example.invalid", "", time.Second)
	for _, p := range []string{"https://evil.invalid", "//evil.invalid", "/x?secret=y", "/x#y", "/x\\y"} {
		if _, _, e := c.Request(context.Background(), "GET", p, nil, nil); output.Normalize(e).Code != 2 {
			t.Fatal(p)
		}
	}
}
func TestCancellation(t *testing.T) {
	c, _ := New("http://127.0.0.1:1", "", time.Second)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, _, e := c.Request(ctx, "PATCH", "/x", nil, []byte(`{}`))
	v := output.Normalize(e)
	if v.Code != 130 || v.Outcome != "unknown" {
		t.Fatalf("%+v", v)
	}
}

func TestPackageDiagnosticsAreBoundedAndDoNotEchoProtectedMessages(t *testing.T) {
	for _, version := range []string{"1.0", "2.0"} {
		t.Run(version, func(t *testing.T) {
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusUnprocessableEntity)
				_, _ = w.Write([]byte(`{"data":{"package_schema_version":"` + version + `","diagnostics":[{"code":"PACKAGE_SCHEMA_INVALID","file":"knowledge-1.yaml","path":"/spec/vector_snapshot","message":"private-provider-secret","input":"private-provider-secret"}]}}`))
			}))
			defer s.Close()
			client, _ := New(s.URL, "fixture", time.Second)
			_, _, err := client.Request(context.Background(), "POST", "/projects/p/packages/export", nil, nil)
			failure := output.Normalize(err)
			if failure.Code != 2 || failure.DomainCode != "PACKAGE_SCHEMA_INVALID" || len(failure.Diagnostics) != 1 || failure.Diagnostics[0].Path != "/spec/vector_snapshot" {
				t.Fatalf("missing structured diagnostic: %+v", failure)
			}
			encoded, _ := json.Marshal(failure)
			if bytes.Contains(encoded, []byte("private-provider-secret")) {
				t.Fatal("protected message copied into diagnostic")
			}
		})
	}
}

func TestPackageExportIncompleteMessagesUseOnlyExactKnownReasons(t *testing.T) {
	for _, tc := range []struct{ message, expected string }{
		{"Snapshot has no complete ModelSpec", "has no complete ModelSpec"},
		{"Snapshot credential intent is unavailable", "has no Provider credential binding"},
		{"Snapshot credential provider differs", "use different Providers"},
		{"Project Environment requirement is unavailable", "Project Environment field is unavailable"},
		{"Snapshot has no complete ModelSpec: private-provider-secret", "server rejected request"},
		{"private-provider-secret", "server rejected request"},
	} {
		t.Run(tc.message, func(t *testing.T) {
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusUnprocessableEntity)
				json.NewEncoder(w).Encode(map[string]any{"data": map[string]any{"package_schema_version": "1.0", "diagnostics": []map[string]any{{"code": "PACKAGE_EXPORT_INCOMPLETE", "message": tc.message, "input": "private-provider-secret", "file": "agent-1.yaml", "path": "/spec/model/primary"}}}})
			}))
			defer s.Close()
			client, _ := New(s.URL, "fixture", time.Second)
			_, _, err := client.Request(context.Background(), "POST", "/projects/p/packages/export", nil, nil)
			failure := output.Normalize(err)
			if failure.Code != 2 || failure.DomainCode != "PACKAGE_EXPORT_INCOMPLETE" || failure.Outcome != "rejected" || !strings.Contains(failure.Message, tc.expected) {
				t.Fatalf("%+v", failure)
			}
			encoded, _ := json.Marshal(failure)
			if bytes.Contains(encoded, []byte("private-provider-secret")) {
				t.Fatal("untrusted diagnostic leaked")
			}
		})
	}
}

func TestASaCDiagnosticsKeepCodesWithoutProtectedMessages(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(409)
		_, _ = w.Write([]byte(`{"data":{"asac_schema_version":"1.0","diagnostics":[{"code":"ASAC_DRAFT_CHANGED","message":"private-provider-secret","input":"private-provider-secret"}]}}`))
	}))
	defer server.Close()
	client, _ := New(server.URL, "fixture", time.Second)
	_, _, err := client.Request(context.Background(), "PUT", "/projects/p/agents/a/asac/drafts/d", nil, []byte("{}"))
	failure := output.Normalize(err)
	if failure.Code != 6 || failure.DomainCode != "ASAC_DRAFT_CHANGED" || failure.Outcome != "rejected" || strings.Contains(failure.Message, "private-provider-secret") {
		t.Fatal(failure)
	}
}

func TestManagedLifecycleCodesOnReviewedLegacyAndPolicyRoutes(t *testing.T) {
	id := "550e8400-e29b-41d4-a716-446655440000"
	for _, path := range []string{
		"/ai/agents/" + id + "/releases/" + id + "/promote",
		"/ai/agents/" + id + "/releases/" + id + "/rollback",
		"/network/" + id + "/promotions",
		"/network/" + id + "/production/activations",
		"/core/projects/" + id + "/lifecycle-policy",
		"/core/projects/" + id + "/lifecycle-policy/operations/" + id,
		"/unreviewed/lifecycle-policy",
	} {
		t.Run(path, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(409)
				_, _ = w.Write([]byte(`{"data":{"asac_schema_version":"1.0","diagnostics":[{"code":"ASAC_PROJECT_MANAGED_LIFECYCLE_REQUIRED","message":"protected-input","input":"protected-input"}]}}`))
			}))
			defer server.Close()
			client, _ := New(server.URL, "fixture", time.Second)
			_, _, err := client.Request(context.Background(), "POST", path, nil, []byte("{}"))
			failure := output.Normalize(err)
			if failure.Code != 6 || failure.Outcome != "rejected" || strings.Contains(failure.Message, "protected-input") {
				t.Fatal(failure)
			}
			if strings.HasPrefix(path, "/unreviewed/") {
				if failure.DomainCode != "" || len(failure.Diagnostics) != 0 {
					t.Fatal("unreviewed route claimed ASaC diagnostics")
				}
			} else if failure.DomainCode != "ASAC_PROJECT_MANAGED_LIFECYCLE_REQUIRED" || len(failure.Diagnostics) != 1 {
				t.Fatal("missing bounded managed lifecycle code", failure)
			}
		})
	}
}

func TestCandidateBindingDiagnosticsLocateComponentAndGiveSafeRecovery(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(422)
		_, _ = w.Write([]byte(`{"data":{"asac_schema_version":"1.0","diagnostics":[{"code":"ASAC_CANDIDATE_BINDING_UNAVAILABLE","file":"agents/support.yaml","path":"/metadata/key","message":"private-provider-secret"}]}}`))
	}))
	defer server.Close()
	client, _ := New(server.URL, "fixture", time.Second)
	_, _, err := client.Request(context.Background(), "POST", "/projects/project/networks/network/asac/candidates", nil, nil)
	failure := output.Normalize(err)
	if failure.DomainCode != "ASAC_CANDIDATE_BINDING_UNAVAILABLE" || len(failure.Diagnostics) != 1 || failure.Diagnostics[0].File != "agents/support.yaml" || !strings.Contains(failure.Message, "managed push") || strings.Contains(failure.Message, "private-provider") {
		t.Fatal(err)
	}
}

func TestLocalDeployDiagnosticsGiveBoundedRecovery(t *testing.T) {
	for code, guidance := range map[string]string{"ASAC_ORIGIN_MISMATCH": "another target", "ASAC_SOURCE_CHANGED": "preserve local edits", "ASAC_HISTORY_INCOMPLETE": "checkpoint exact parents"} {
		t.Run(code, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(409)
				_, _ = w.Write([]byte(`{"data":{"asac_schema_version":"1.0","diagnostics":[{"code":"` + code + `","message":"private-provider-secret"}]}}`))
			}))
			defer server.Close()
			client, _ := New(server.URL, "fixture", time.Second)
			_, _, err := client.Request(context.Background(), "GET", "/projects/project/agents/agent/asac/drafts/preflight", nil, nil)
			failure := output.Normalize(err)
			if failure.DomainCode != code || !strings.Contains(failure.Message, guidance) || strings.Contains(failure.Message, "private-provider") {
				t.Fatal(err)
			}
		})
	}
}
